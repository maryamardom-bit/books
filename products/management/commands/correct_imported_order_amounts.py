"""
Correction tooling for imported WooCommerce order totals (P0-2). Dry-run by default.

Four modes, each producing an artifact that the next one verifies:

  --snapshot  Read-only. Classifies every imported order against the WXR export and writes the
              before-state CSV (original values, rule, proposed value) plus a manifest with its
              SHA-256, per-rule counts and sums, a fingerprint of all imported orders, the
              database identity and the classification policy (with its SHA-256).
  (default)   Read-only preview. Re-validates the before-state (hash, structure, rules, factors,
              policy) against the current database and writes a deterministic preview that
              separates proposed corrections, owner-review rows, rejected rows and conflicts, plus
              an unsigned approval request listing every value an approval must bind.
  --apply     Compare-and-set update of exactly one rule batch.
  --rollback  Compare-and-set restore of one committed batch, driven by its execution report.

--apply and --rollback are disabled in code (EXECUTION_ENABLED). Even when enabled they refuse
unless the approval file's SHA-256 is recorded in AUTHORIZED_APPROVALS by a reviewed code change,
the anomaly registry holds the owner-approved ids, the reviewed wholesale threshold was used, the
connected PostgreSQL database is the one recorded in the before-state, and the required
migrations are applied.

The conversion factors in core.money are provisional. Equality between a stored value and a
provisional conversion is a numerical observation only: it is never evidence that a factor or a
correction was approved. Rows that need rounding are never proposed; the owner decides them.
"""

import csv
import hashlib
import io
import json
import os
import re
from collections import Counter, defaultdict
from contextlib import contextmanager
from decimal import Inexact, localcontext
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, DatabaseError, OperationalError, connections, transaction
from django.db.models import Sum
from django.utils import timezone

from core.money import TOMAN_PER_UNIT, MoneyConversionError, normalize_currency, parse_amount
from products.management.commands.audit_imported_order_amounts import (
    DEFAULT_WHOLESALE_THRESHOLD,
    DUPLICATE_IN_DB,
    DUPLICATE_IN_EXPORT,
    FLAG_CANCELLED_SEP_ANOMALY,
    FLAG_HAS_REFUND_RECORD,
    FLAG_INVALID_AMOUNT,
    FLAG_INVALID_CURRENCY,
    FLAG_INVALID_ID,
    FLAG_IRR_NOT_DIVISIBLE_BY_10,
    FLAG_REFUNDED_STATUS,
    FLAG_WHOLESALE_SIZED,
    FLAG_ZERO_TOTAL,
    LARGE_IRHT_SOURCE_UNITS,
    MATCH,
    MISMATCH,
    MISSING_IN_EXPORT,
    RAW_IRHT,
    RAW_IRR,
    SOURCE_INVALID,
    load_export,
    reconcile,
)

# Real execution stays off until a reviewed code change enables it for an approved run.
EXECUTION_ENABLED = False

# WordPress ids of the two cancelled SEP IRHT anomalies (Phase 3 plan, section 1.5), as approved by
# the owner after looking them up in WooCommerce and the SEP panel. Empty: the ids have not been
# provided or approved, so --apply and --rollback refuse. Only a reviewed code change may fill it.
APPROVED_ANOMALY_WORDPRESS_IDS = frozenset()
EXPECTED_ANOMALY_COUNT = 2

# Approval file SHA-256 -> approval_ref, recorded through the designated approval process (a reviewed
# code change). The SHA-256 on the command line only proves file integrity, not authorisation.
AUTHORIZED_APPROVALS = {}

# The only wholesale threshold a batch may be applied with (it splits R1A from R1B).
REVIEWED_WHOLESALE_THRESHOLD = DEFAULT_WHOLESALE_THRESHOLD

BEFORE_STATE_FORMAT = 'kasra-order-amount-before-state/v2'
APPROVAL_FORMAT = 'kasra-order-amount-correction-approval/v2'
POLICY_VERSION = 'kasra-order-amount-classification/v2'
ADVISORY_LOCK_KEY = 0x4B415352_02  # 'KASR' + P0-2; also held by the order importer
BIGINT_MAX = 9223372036854775807
FACTOR_STATUS = 'PROVISIONAL_UNAPPROVED'
ID_CHUNK = 1000
REQUIRED_MIGRATION_APPS = ('orders', 'payment')
IDENTITY_REQUIRED = ('database_name', 'database_oid', 'system_identifier', 'server_version_num')
IDENTITY_COMPARED = IDENTITY_REQUIRED + ('cluster_name',)

NOTICE = (
    'Conversion factors are provisional and unapproved. Numerical equality with a provisional '
    'conversion is not evidence of approval. Nothing in this output is approved.'
)

BEFORE_STATE_COLUMNS = [
    'order_id', 'wordpress_id', 'total_price_before', 'is_paid_before', 'has_payment',
    'source_status', 'source_currency', 'source_amount', 'audit_classification', 'flags',
    'rule', 'reason_code', 'factor', 'proposed_after',
]
PREVIEW_COLUMNS = [
    'category', 'reason_code', 'rule', 'order_id', 'wordpress_id', 'source_currency', 'source_amount',
    'factor', 'factor_status', 'total_price_before', 'total_price_current', 'proposed_after', 'delta',
]
# total_price_before / total_price_after keep their correction meaning in rollback reports too.
EXECUTION_COLUMNS = [
    'status', 'order_id', 'wordpress_id', 'rule', 'reason_code', 'source_currency', 'factor',
    'total_price_before', 'total_price_after', 'approval_ref', 'approval_sha256',
    'before_state_sha256', 'preview_sha256', 'execution_report_sha256',
]

CORRECTION_REASONS = {
    'R1A': 'R1A_IRR_DIV10',
    'R1B': 'R1B_IRR_DIV10_WHOLESALE',
    'R2': 'R2_IRHT_X1000',
    'R4': 'R4_CANCELLED_CONVERT',
    'R5': 'R5_REFUND_RELATED_CONVERT',
}
CORRECTABLE_RULES = tuple(CORRECTION_REASONS)
ALL_RULES = ('R1A', 'R1B', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8')
PRECEDENCE = ('R7', 'R3', 'R8', 'R6', 'R5', 'R4', 'R2', 'R1B', 'R1A')

PROPOSED = 'PROPOSED'
ALREADY_APPLIED = 'ALREADY_APPLIED'
NOT_SELECTED = 'NOT_SELECTED'
NO_CHANGE = 'NO_CHANGE'
OWNER_REVIEW = 'OWNER_REVIEW'
REJECTED = 'REJECTED'
CONFLICT = 'CONFLICT'
CATEGORY_ORDER = (PROPOSED, ALREADY_APPLIED, CONFLICT, OWNER_REVIEW, REJECTED, NOT_SELECTED, NO_CHANGE)

REVIEW_REASONS = {
    'EXCL_R7_APPROVED_ANOMALY_ID', 'EXCL_R7_ANOMALY', 'REVIEW_LARGE_IRHT', 'REVIEW_ROUNDING_REQUIRED',
    'REVIEW_STORED_EQUALS_PROVISIONAL_CONVERSION', 'EXCL_R8_UNMAPPED_STATUS',
}
KNOWN_FLAGS = {
    FLAG_ZERO_TOTAL, FLAG_REFUNDED_STATUS, FLAG_HAS_REFUND_RECORD, FLAG_WHOLESALE_SIZED,
    FLAG_CANCELLED_SEP_ANOMALY, FLAG_IRR_NOT_DIVISIBLE_BY_10, FLAG_INVALID_AMOUNT,
    FLAG_INVALID_CURRENCY, FLAG_INVALID_ID,
}
KNOWN_CLASSIFICATIONS = {
    MATCH, RAW_IRR, RAW_IRHT, MISMATCH, MISSING_IN_EXPORT, DUPLICATE_IN_EXPORT, DUPLICATE_IN_DB, SOURCE_INVALID,
}
_SHA256 = re.compile(r'[0-9a-f]{64}')
_STATUS = re.compile(r'[a-z0-9_-]{1,40}')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_sha256(value, label):
    text = (value or '').strip().lower()
    if not _SHA256.fullmatch(text):
        raise CommandError(f'{label} must be a 64-character hexadecimal SHA-256.')
    return text


def _canonical(amount):
    return format(amount, 'f')


def _chunks(ids, size=None):
    size = size or ID_CHUNK
    for start in range(0, len(ids), size):
        yield ids[start:start + size]


def _exact_conversion(amount, factor):
    """amount * factor as an exact Decimal; never rounds."""
    with localcontext() as ctx:
        _, digits, exponent = amount.as_tuple()
        ctx.prec = max(28, len(digits) + abs(exponent) + 10)
        ctx.traps[Inexact] = True
        return amount * factor


def _is_large_irht(currency, amount):
    return currency == 'IRHT' and amount is not None and amount > LARGE_IRHT_SOURCE_UNITS


def classify(audit_classification, status, currency, amount, stored, flags, has_payment, wordpress_id=None):
    """
    Apply the correction matrix (precedence R7, R3, R8, R6, R5, R4, R2, R1B, R1A).
    Return (rule, reason_code, factor, proposed_after); factor and proposed_after are '' when not
    applicable. A proposed value is only produced for an exact conversion of a raw stored total.
    An approved anomaly id is excluded before anything else is looked at, and a large IRHT total
    always goes to owner review, whatever its status, payment method or the wholesale threshold.
    """
    if wordpress_id is not None and wordpress_id in APPROVED_ANOMALY_WORDPRESS_IDS:
        return 'R7', 'EXCL_R7_APPROVED_ANOMALY_ID', '', ''
    if FLAG_CANCELLED_SEP_ANOMALY in flags:
        return 'R7', 'EXCL_R7_ANOMALY', '', ''
    if audit_classification == MATCH and FLAG_ZERO_TOTAL in flags and stored == 0:
        return 'R3', 'EXCL_R3_ZERO', '', ''
    if audit_classification == MATCH:
        return 'R8', 'REVIEW_STORED_EQUALS_PROVISIONAL_CONVERSION', '', ''
    if audit_classification not in (RAW_IRR, RAW_IRHT):
        return 'R8', f'EXCL_R8_{audit_classification}', '', ''
    if amount is None or currency not in TOMAN_PER_UNIT:
        return 'R8', 'EXCL_R8_SOURCE_INVALID', '', ''
    if amount != amount.to_integral_value():
        return 'R8', 'EXCL_R8_SOURCE_NOT_INTEGER', '', ''
    if stored != int(amount):
        return 'R8', 'EXCL_R8_STORED_NOT_RAW', '', ''
    if has_payment:
        return 'R6', 'EXCL_R6_HAS_PAYMENT', '', ''
    if status == 'wc-refunded' or FLAG_HAS_REFUND_RECORD in flags:
        rule = 'R5'
    elif status == 'wc-cancelled':
        rule = 'R4'
    elif status in ('wc-completed', 'wc-on-hold'):
        if currency == 'IRHT':
            rule = 'R2'
        elif currency == 'IRR':
            rule = 'R1B' if FLAG_WHOLESALE_SIZED in flags else 'R1A'
        else:
            return 'R8', 'EXCL_R8_UNMAPPED_CURRENCY', '', ''
    else:
        return 'R8', 'EXCL_R8_UNMAPPED_STATUS', '', ''
    if _is_large_irht(currency, amount):
        return rule, 'REVIEW_LARGE_IRHT', '', ''
    factor = TOMAN_PER_UNIT[currency]
    converted = _exact_conversion(amount, factor)
    if converted != converted.to_integral_value():
        return rule, 'REVIEW_ROUNDING_REQUIRED', str(factor), ''
    after = int(converted)
    if after <= 0 or after > BIGINT_MAX:
        return rule, 'REJECT_OUT_OF_RANGE', str(factor), ''
    return rule, CORRECTION_REASONS[rule], str(factor), after


def base_category(reason_code):
    if reason_code in CORRECTION_REASONS.values():
        return PROPOSED
    if reason_code == 'EXCL_R3_ZERO':
        return NO_CHANGE
    if reason_code in REVIEW_REASONS:
        return OWNER_REVIEW
    return REJECTED


def _csv_bytes(columns, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(columns)
    for row in rows:
        writer.writerow(['' if row.get(c) is None else row[c] for c in columns])
    return buffer.getvalue().encode('utf-8')


def _json_bytes(data):
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode('utf-8')


def _factor_table():
    return {code: {'toman_per_unit': str(factor), 'status': FACTOR_STATUS} for code, factor in sorted(TOMAN_PER_UNIT.items())}


def classification_policy():
    """Everything that decides which rows are eligible; bound by hash to the before-state and approval."""
    return {
        'version': POLICY_VERSION,
        'precedence': list(PRECEDENCE),
        'anomaly_wordpress_ids': sorted(APPROVED_ANOMALY_WORDPRESS_IDS),
        'anomaly_flag': FLAG_CANCELLED_SEP_ANOMALY,
        'large_irht_review_above_source_units': str(LARGE_IRHT_SOURCE_UNITS),
        'reviewed_wholesale_threshold_toman': str(REVIEWED_WHOLESALE_THRESHOLD),
        'correction_reasons': dict(CORRECTION_REASONS),
        'review_reasons': sorted(REVIEW_REASONS),
        'conversion_factors': _factor_table(),
    }


def policy_sha256(policy):
    return sha256_bytes(_json_bytes(policy))


class Outputs:
    """
    Output files are created exclusively before any work starts, so an existing or unwritable
    destination fails early. On failure the incomplete files are removed unless kept explicitly.
    """

    def __init__(self, *paths):
        self.paths = [Path(p) for p in paths]
        self.handles = {}

    def reserve(self):
        for path in self.paths:
            if path.exists():
                raise CommandError(f'{path} already exists; choose a new output path.')
            if not path.parent.is_dir():
                raise CommandError(f'Output directory does not exist: {path.parent}')
        try:
            for path in self.paths:
                self.handles[path] = path.open('xb')
        except OSError as exc:
            self.discard()
            raise CommandError(f'Cannot create output file: {exc.strerror or exc}') from None
        return self

    def write(self, path, data):
        handle = self.handles[Path(path)]
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())

    def close(self):
        for handle in self.handles.values():
            handle.close()

    def discard(self):
        self.close()
        for path in self.handles:
            try:
                path.unlink()
            except OSError:
                pass
        self.handles = {}


# ---------------------------------------------------------------- database access

@contextmanager
def read_only(using):
    """
    Every read runs in its own REPEATABLE READ, READ ONLY transaction on PostgreSQL, so orders and
    payments are read from one snapshot. It must be the outermost transaction: SET TRANSACTION is
    rejected or silently scoped once another transaction has run a query.
    """
    connection = connections[using]
    if connection.in_atomic_block:
        raise CommandError('The correction command must not run inside an existing transaction.')
    with transaction.atomic(using=using):
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        yield


@contextmanager
def write_transaction(using, expected_identity):
    """
    REPEATABLE READ transaction whose first statement sets the isolation level, then the
    transaction-level advisory lock, then the identity check. PostgreSQL only.
    """
    connection = connections[using]
    if connection.vendor != 'postgresql':
        raise CommandError(f'Writes are only supported on PostgreSQL (connected: {connection.vendor}); nothing was changed.')
    if connection.in_atomic_block:
        raise CommandError('The correction command must not run inside an existing transaction.')
    with transaction.atomic(using=using):
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cursor.execute('SELECT pg_try_advisory_xact_lock(%s)', [ADVISORY_LOCK_KEY])
            if not cursor.fetchone()[0]:
                raise CommandError('Another correction, rollback or order import holds the advisory lock; nothing was changed.')
        check_identity(expected_identity, database_identity(using))
        yield


def database_identity(using):
    """Identity of the connected database; on PostgreSQL the system identifier names the cluster."""
    connection = connections[using]
    identity = {'vendor': connection.vendor}
    if connection.vendor != 'postgresql':
        return identity
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_database(), (SELECT oid FROM pg_database WHERE datname = current_database())::text, "
            "current_setting('server_version_num'), current_setting('cluster_name')"
        )
        name, oid, version, cluster = cursor.fetchone()
    identity.update(database_name=name, database_oid=oid, server_version_num=version, cluster_name=cluster)
    try:
        with transaction.atomic(using=using):
            with connection.cursor() as cursor:
                cursor.execute('SELECT system_identifier::text FROM pg_control_system()')
                identity['system_identifier'] = cursor.fetchone()[0]
    except DatabaseError:
        identity['system_identifier'] = None
    return identity


def check_identity(expected, actual):
    if actual.get('vendor') != 'postgresql':
        raise CommandError(f"Only a PostgreSQL target can be verified (connected: {actual.get('vendor')}); refusing.")
    missing = [key for key in IDENTITY_REQUIRED if not actual.get(key)]
    if missing:
        raise CommandError(f"Database identity is incomplete ({', '.join(missing)}); refusing an unverified target.")
    if not isinstance(expected, dict) or any(expected.get(key) != actual.get(key) for key in IDENTITY_COMPARED):
        raise CommandError('The connected database is not the database recorded in the before-state; refusing.')


def check_schema(using):
    """Refuse while migrations of the apps the correction reads or guards are unapplied."""
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connections[using])
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    pending = sorted(f'{m.app_label}.{m.name}' for m, _ in plan if m.app_label in REQUIRED_MIGRATION_APPS)
    if pending:
        raise CommandError(
            f"Unapplied migrations required by the correction: {', '.join(pending)}. They must be applied "
            'through the approved deployment process first; nothing was changed.'
        )


def _payment_order_ids(using):
    from payment.models import Payment

    if Payment._meta.db_table not in connections[using].introspection.table_names():
        return set(), False
    return set(Payment.objects.using(using).values_list('order_id', flat=True).distinct()), True


def _current_orders(using):
    """(pk, wordpress_id, total_price, is_paid) of every order; no personal data is read."""
    from orders.models import Order

    return {
        pk: (wp_id, total, is_paid)
        for pk, wp_id, total, is_paid in Order.objects.using(using)
        .order_by('pk').values_list('pk', 'wordpress_id', 'total_price', 'is_paid')
    }


def imported_fingerprint(current):
    digest = hashlib.sha256()
    count = total = 0
    for pk in sorted(current):
        wp_id, price, is_paid = current[pk]
        if wp_id is None:
            continue
        digest.update(f'{pk},{wp_id},{price},{int(is_paid)}\n'.encode('ascii'))
        count += 1
        total += price
    return {'count': count, 'total_price_sum': str(total), 'sha256': digest.hexdigest()}


def _fingerprint_with(before_rows, corrected_pks):
    """Fingerprint the imported orders would have if exactly corrected_pks held their proposed value."""
    return imported_fingerprint({
        b['order_id']: (
            b['wordpress_id'],
            b['proposed_after'] if b['order_id'] in corrected_pks else b['total_price_before'],
            b['is_paid_before'],
        )
        for b in before_rows
    })


def _rule_totals(rows):
    totals = {}
    for row in rows:
        bucket = totals.setdefault(row['rule'], {'orders': 0, 'total_price_before': 0, 'proposed_after': 0, 'proposed': 0})
        bucket['orders'] += 1
        bucket['total_price_before'] += row['total_price_before']
        if row['proposed_after'] != '':
            bucket['proposed'] += 1
            bucket['proposed_after'] += row['proposed_after']
    return {rule: {k: str(v) for k, v in totals[rule].items()} for rule in sorted(totals)}


def _describe(exc):
    code = getattr(exc.__cause__, 'pgcode', None) or getattr(exc, 'pgcode', None)
    return f'{type(exc).__name__} {code}' if code else type(exc).__name__


# ---------------------------------------------------------------- before-state

def build_before_state(orders, refunds, current, payment_ids, wholesale_threshold):
    """One row per imported order in the database, sorted by wordpress_id."""
    db_rows = [(wp_id, price) for wp_id, price, _ in current.values() if wp_id is not None]
    report = reconcile(orders, refunds, db_rows, wholesale_threshold=wholesale_threshold)
    by_wp = defaultdict(list)
    for row in report.rows:
        if row['record_type'] == 'order' and isinstance(row['wordpress_id'], int):
            by_wp[row['wordpress_id']].append(row)

    rows = []
    for pk, (wp_id, price, is_paid) in current.items():
        if wp_id is None:
            continue
        matches = by_wp.get(wp_id, [])
        source = matches[0] if len(matches) == 1 else None
        classification = source['classification'] if source else DUPLICATE_IN_EXPORT
        if source is None or classification in (DUPLICATE_IN_EXPORT, MISSING_IN_EXPORT, DUPLICATE_IN_DB):
            status = currency = amount_text = ''
            flags = []
            amount = None
        else:
            status = source['source_status'] if _STATUS.fullmatch(source['source_status'] or '') else ''
            try:
                currency = normalize_currency(source['source_currency'])
            except MoneyConversionError:
                currency = ''
            try:
                amount = parse_amount(source['source_amount'])
                amount_text = _canonical(amount)
            except MoneyConversionError:
                amount, amount_text = None, ''
            flags = [f for f in source['flags'].split(';') if f]
        has_payment = pk in payment_ids
        rule, reason, factor, after = classify(classification, status, currency, amount, price, flags, has_payment, wp_id)
        rows.append({
            'order_id': pk, 'wordpress_id': wp_id, 'total_price_before': price, 'is_paid_before': is_paid,
            'has_payment': has_payment, 'source_status': status, 'source_currency': currency,
            'source_amount': amount_text, 'audit_classification': classification, 'flags': ';'.join(sorted(flags)),
            'rule': rule, 'reason_code': reason, 'factor': factor, 'proposed_after': after,
        })
    rows.sort(key=lambda r: (r['wordpress_id'], r['order_id']))
    return rows


def _parse_int(value, field, line, minimum=0, label='Before-state'):
    if not (value.isascii() and value.isdigit()):
        raise CommandError(f'{label} line {line}: {field} is not a non-negative integer.')
    number = int(value)
    if number < minimum or number > BIGINT_MAX:
        raise CommandError(f'{label} line {line}: {field} is out of range.')
    return number


def _parse_bool(value, field, line):
    if value not in ('True', 'False'):
        raise CommandError(f'Before-state line {line}: {field} must be True or False.')
    return value == 'True'


def load_before_state(path, expected_sha256):
    """
    Validate the before-state against its manifest and the hash given by the operator, re-derive
    every rule and proposed value, and return (rows, manifest, sha256). Any defect rejects the
    whole artifact: nothing is guessed or skipped.
    """
    path = Path(path)
    manifest_path = Path(f'{path}.manifest.json')
    if not path.is_file():
        raise CommandError(f'Before-state file not found: {path}')
    if not manifest_path.is_file():
        raise CommandError(f'Before-state manifest not found: {manifest_path}')
    data = path.read_bytes()
    actual = sha256_bytes(data)
    if actual != expected_sha256:
        raise CommandError('Before-state SHA-256 does not match --before-state-sha256; the file was changed or is not the recorded one.')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandError(f'Before-state manifest is not valid JSON ({exc.__class__.__name__}).') from None
    if not isinstance(manifest, dict) or manifest.get('format') != BEFORE_STATE_FORMAT:
        raise CommandError('Before-state manifest has an unknown format.')
    if manifest.get('before_state_sha256') != actual:
        raise CommandError('Before-state manifest records a different SHA-256 than the before-state file.')
    if manifest.get('conversion_factors') != _factor_table():
        raise CommandError('Conversion factors changed since the before-state was recorded; take a new snapshot.')
    policy = classification_policy()
    if manifest.get('classification_policy') != policy or manifest.get('classification_policy_sha256') != policy_sha256(policy):
        raise CommandError('Classification policy changed since the before-state was recorded; take a new snapshot.')
    if not isinstance(manifest.get('database_identity'), dict):
        raise CommandError('Before-state manifest has no database identity.')
    try:
        parse_amount(manifest.get('wholesale_threshold_toman', ''))
    except MoneyConversionError:
        raise CommandError('Before-state manifest has an invalid wholesale threshold.') from None

    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise CommandError('Before-state file is not valid UTF-8.') from None
    reader = csv.reader(io.StringIO(text, newline=''))
    header = next(reader, None)
    if header != BEFORE_STATE_COLUMNS:
        raise CommandError('Before-state header does not match the expected columns.')

    rows, order_ids, wp_ids = [], set(), set()
    for line, values in enumerate(reader, start=2):
        if len(values) != len(BEFORE_STATE_COLUMNS):
            raise CommandError(f'Before-state line {line}: expected {len(BEFORE_STATE_COLUMNS)} columns.')
        raw = dict(zip(BEFORE_STATE_COLUMNS, values))
        row = {
            'order_id': _parse_int(raw['order_id'], 'order_id', line, minimum=1),
            'wordpress_id': _parse_int(raw['wordpress_id'], 'wordpress_id', line, minimum=1),
            'total_price_before': _parse_int(raw['total_price_before'], 'total_price_before', line),
            'is_paid_before': _parse_bool(raw['is_paid_before'], 'is_paid_before', line),
            'has_payment': _parse_bool(raw['has_payment'], 'has_payment', line),
            'source_status': raw['source_status'],
            'source_currency': raw['source_currency'],
            'source_amount': raw['source_amount'],
            'audit_classification': raw['audit_classification'],
            'flags': raw['flags'],
            'rule': raw['rule'],
            'reason_code': raw['reason_code'],
            'factor': raw['factor'],
            'proposed_after': raw['proposed_after'],
        }
        if row['order_id'] in order_ids or row['wordpress_id'] in wp_ids:
            raise CommandError(f'Before-state line {line}: duplicate order_id or wordpress_id.')
        order_ids.add(row['order_id'])
        wp_ids.add(row['wordpress_id'])
        if row['source_status'] and not _STATUS.fullmatch(row['source_status']):
            raise CommandError(f'Before-state line {line}: malformed source_status.')
        if row['source_currency'] and row['source_currency'] not in TOMAN_PER_UNIT:
            raise CommandError(f'Before-state line {line}: unsupported source_currency.')
        if row['audit_classification'] not in KNOWN_CLASSIFICATIONS:
            raise CommandError(f'Before-state line {line}: unknown audit_classification.')
        flags = [f for f in row['flags'].split(';') if f]
        if not set(flags) <= KNOWN_FLAGS:
            raise CommandError(f'Before-state line {line}: unknown flag.')
        amount = None
        if row['source_amount']:
            try:
                amount = parse_amount(row['source_amount'])
            except MoneyConversionError:
                raise CommandError(f'Before-state line {line}: malformed source_amount.') from None
            if _canonical(amount) != row['source_amount']:
                raise CommandError(f'Before-state line {line}: source_amount is not in canonical form.')
        expected = classify(
            row['audit_classification'], row['source_status'], row['source_currency'], amount,
            row['total_price_before'], flags, row['has_payment'], row['wordpress_id'],
        )
        recorded = (row['rule'], row['reason_code'], row['factor'], row['proposed_after'])
        if tuple('' if v == '' else str(v) for v in expected) != recorded:
            raise CommandError(
                f'Before-state line {line}: rule, reason, factor or proposed value does not match the '
                'correction rules; the artifact is inconsistent or was edited.'
            )
        row['proposed_after'] = expected[3]
        rows.append(row)

    if manifest.get('rows') != len(rows):
        raise CommandError('Before-state row count does not match the manifest.')
    if manifest.get('rules') != _rule_totals(rows):
        raise CommandError('Before-state per-rule counts or sums do not match the manifest.')
    return rows, manifest, actual


def check_reviewed_threshold(manifest):
    if parse_amount(manifest['wholesale_threshold_toman']) != REVIEWED_WHOLESALE_THRESHOLD:
        raise CommandError(
            f"The before-state was taken with wholesale threshold {manifest['wholesale_threshold_toman']}; only the "
            f'reviewed value {REVIEWED_WHOLESALE_THRESHOLD} may be applied. Take a new snapshot.'
        )


def check_anomaly_registry(before_rows):
    """The registry must hold the owner-approved ids, and they must be exactly the anomalies seen in the data."""
    ids = APPROVED_ANOMALY_WORDPRESS_IDS
    if len(ids) != EXPECTED_ANOMALY_COUNT:
        raise CommandError(
            f'APPROVED_ANOMALY_WORDPRESS_IDS holds {len(ids)} ids; the {EXPECTED_ANOMALY_COUNT} owner-approved ids of '
            'the cancelled SEP anomalies are required before any batch may run.'
        )
    by_wp = {row['wordpress_id']: row for row in before_rows}
    for wp_id in sorted(ids):
        if by_wp.get(wp_id, {}).get('rule') != 'R7':
            raise CommandError(f'Approved anomaly id {wp_id} is not an R7 row of the before-state; refusing.')
    flagged = {row['wordpress_id'] for row in before_rows if FLAG_CANCELLED_SEP_ANOMALY in row['flags'].split(';')}
    if not flagged <= ids:
        raise CommandError(f'{len(flagged - ids)} rows flagged {FLAG_CANCELLED_SEP_ANOMALY} are not in the approved anomaly registry; refusing.')


def assert_batch_eligible(before_rows, order_ids, rule):
    """Independent re-check of every row about to be written, against the before-state."""
    by_pk = {row['order_id']: row for row in before_rows}
    for pk in order_ids:
        row = by_pk.get(pk)
        amount = parse_amount(row['source_amount']) if row and row['source_amount'] else None
        if (row is None or row['rule'] != rule or row['reason_code'] != CORRECTION_REASONS[rule]
                or row['wordpress_id'] in APPROVED_ANOMALY_WORDPRESS_IDS
                or FLAG_CANCELLED_SEP_ANOMALY in row['flags'].split(';')
                or _is_large_irht(row['source_currency'], amount)
                or row['factor'] != str(TOMAN_PER_UNIT.get(row['source_currency']))
                or row['proposed_after'] != int(_exact_conversion(amount, TOMAN_PER_UNIT[row['source_currency']]))):
            raise CommandError(f'Order {pk} is not eligible for {rule}; refusing the whole batch.')


# ---------------------------------------------------------------- preview

def build_preview(before_rows, current, payment_ids, selected_rules):
    selected = set(selected_rules or CORRECTABLE_RULES)
    known_pks = set()
    rows = []
    for b in before_rows:
        known_pks.add(b['order_id'])
        category = base_category(b['reason_code'])
        reason = b['reason_code']
        if category == PROPOSED and b['rule'] not in selected:
            category = NOT_SELECTED
        now = current.get(b['order_id'])
        current_total = '' if now is None else now[1]
        drift = None
        if now is None:
            drift = 'DB_ORDER_MISSING'
        elif now[0] != b['wordpress_id']:
            drift = 'DB_WORDPRESS_ID_CHANGED'
        elif now[2] != b['is_paid_before']:
            drift = 'DB_IS_PAID_CHANGED'
        elif b['order_id'] in payment_ids and not b['has_payment']:
            drift = 'DB_PAYMENT_ADDED'
        elif now[1] != b['total_price_before']:
            if b['proposed_after'] != '' and now[1] == b['proposed_after']:
                category, reason = ALREADY_APPLIED, f"ALREADY_APPLIED_{b['reason_code']}"
            else:
                drift = 'DB_TOTAL_CHANGED'
        if drift:
            category, reason = CONFLICT, drift
        after = b['proposed_after']
        rows.append({
            'category': category, 'reason_code': reason, 'rule': b['rule'], 'order_id': b['order_id'],
            'wordpress_id': b['wordpress_id'], 'source_currency': b['source_currency'],
            'source_amount': b['source_amount'], 'factor': b['factor'],
            'factor_status': FACTOR_STATUS if b['factor'] else '',
            'total_price_before': b['total_price_before'], 'total_price_current': current_total,
            'proposed_after': after, 'delta': '' if after == '' else after - b['total_price_before'],
            'is_paid_before': b['is_paid_before'],
        })
    for pk in sorted(current):
        wp_id, price, _ = current[pk]
        if wp_id is not None and pk not in known_pks:
            rows.append({
                'category': CONFLICT, 'reason_code': 'NOT_IN_BEFORE_STATE', 'rule': '', 'order_id': pk,
                'wordpress_id': wp_id, 'total_price_current': price,
            })
    rows.sort(key=lambda r: (CATEGORY_ORDER.index(r['category']), r['wordpress_id'], r['order_id']))
    return rows


def apply_blockers(manifest, identity, fingerprint_matches, rows):
    blockers = []
    if not EXECUTION_ENABLED:
        blockers.append('EXECUTION_DISABLED_IN_CODE')
    if len(APPROVED_ANOMALY_WORDPRESS_IDS) != EXPECTED_ANOMALY_COUNT:
        blockers.append('ANOMALY_REGISTRY_NOT_OWNER_APPROVED')
    if not AUTHORIZED_APPROVALS:
        blockers.append('NO_AUTHORIZED_APPROVAL_RECORDED')
    if parse_amount(manifest['wholesale_threshold_toman']) != REVIEWED_WHOLESALE_THRESHOLD:
        blockers.append('WHOLESALE_THRESHOLD_NOT_REVIEWED')
    try:
        check_identity(manifest['database_identity'], identity)
    except CommandError:
        blockers.append('DATABASE_IDENTITY_NOT_VERIFIED')
    if not fingerprint_matches:
        blockers.append('IMPORTED_ORDERS_CHANGED_SINCE_BEFORE_STATE')
    if any(r['category'] == CONFLICT for r in rows):
        blockers.append('CONFLICTS_PRESENT')
    return blockers


def preview_summary(rows, before_sha, manifest, current, selected_rules, identity):
    proposed = defaultdict(lambda: {'orders': 0, 'total_price_before': 0, 'proposed_after': 0})
    currencies = set()
    for row in rows:
        if row['category'] == PROPOSED:
            bucket = proposed[row['rule']]
            bucket['orders'] += 1
            bucket['total_price_before'] += row['total_price_before']
            bucket['proposed_after'] += row['proposed_after']
            currencies.add(row['source_currency'])
    fingerprint = imported_fingerprint(current)
    matches = fingerprint == manifest.get('imported_orders_fingerprint')
    return {
        'mode': 'DRY_RUN',
        'notice': NOTICE,
        'before_state_sha256': before_sha,
        'selected_rules': sorted(selected_rules or CORRECTABLE_RULES),
        'conversion_factors': _factor_table(),
        'classification_policy_sha256': manifest['classification_policy_sha256'],
        'wholesale_threshold_toman': manifest['wholesale_threshold_toman'],
        'categories': {c: sum(1 for r in rows if r['category'] == c) for c in CATEGORY_ORDER},
        'reasons': dict(sorted(Counter(r['reason_code'] for r in rows).items())),
        'proposed_by_rule': {rule: {k: str(v) for k, v in proposed[rule].items()} for rule in sorted(proposed)},
        'proposed_currencies': sorted(currencies),
        'imported_orders_fingerprint': {'current': fingerprint, 'matches_before_state': matches},
        'database_identity': {'before_state': manifest['database_identity'], 'current': identity},
        'apply_blockers': apply_blockers(manifest, identity, matches, rows),
    }


def approval_request(summary, manifest, preview_sha):
    """Unsigned list of every value an approval for this single-rule preview must bind."""
    return {
        'format': APPROVAL_FORMAT,
        'approval_ref': None,
        'before_state_sha256': summary['before_state_sha256'],
        'preview_sha256': preview_sha,
        'rules': summary['selected_rules'],
        'currency_factors': {
            code: {'toman_per_unit': str(TOMAN_PER_UNIT[code]), 'evidence_ref': None}
            for code in summary['proposed_currencies']
        },
        'classification_policy_sha256': manifest['classification_policy_sha256'],
        'wholesale_threshold_toman': manifest['wholesale_threshold_toman'],
        'anomaly_wordpress_ids': manifest['classification_policy']['anomaly_wordpress_ids'],
        'database_identity': manifest['database_identity'],
        'imported_orders_fingerprint_sha256': manifest['imported_orders_fingerprint']['sha256'],
    }


def summary_lines(summary, preview_sha):
    lines = [
        '== Order amount correction preview (DRY RUN: no data was changed) ==',
        f"before_state_sha256={summary['before_state_sha256']}",
        f"selected_rules={','.join(summary['selected_rules'])}",
        f"classification_policy_sha256={summary['classification_policy_sha256']}",
        f"wholesale_threshold_toman={summary['wholesale_threshold_toman']}",
        f"NOTICE: {summary['notice']}",
    ]
    for code, info in summary['conversion_factors'].items():
        lines.append(f"  factor {code}: toman_per_unit={info['toman_per_unit']} status={info['status']}")
    for category, count in summary['categories'].items():
        lines.append(f'  category {category}: {count}')
    for reason, count in summary['reasons'].items():
        lines.append(f'  reason {reason}: {count}')
    for rule, info in summary['proposed_by_rule'].items():
        lines.append(f"  proposed {rule}: orders={info['orders']} before_sum={info['total_price_before']} after_sum={info['proposed_after']}")
    fp = summary['imported_orders_fingerprint']
    lines.append(f"imported orders: count={fp['current']['count']} sum={fp['current']['total_price_sum']} "
                 f"fingerprint={'MATCHES_BEFORE_STATE' if fp['matches_before_state'] else 'CHANGED_SINCE_BEFORE_STATE'}")
    lines.append(f"apply_blockers={','.join(summary['apply_blockers']) or 'NONE'}")
    lines.append(f'preview_sha256={preview_sha}')
    return lines


# ---------------------------------------------------------------- approval

APPROVAL_KEYS = {
    'format', 'approval_ref', 'before_state_sha256', 'preview_sha256', 'rules', 'currency_factors',
    'classification_policy_sha256', 'wholesale_threshold_toman', 'anomaly_wordpress_ids',
    'database_identity', 'imported_orders_fingerprint_sha256',
}


def load_approval(path, expected_sha256, before_sha, manifest, rule):
    path = Path(path)
    if not path.is_file():
        raise CommandError(f'Approval file not found: {path}')
    data = path.read_bytes()
    if sha256_bytes(data) != expected_sha256:
        raise CommandError('Approval file SHA-256 does not match --approval-sha256.')
    authorized_ref = AUTHORIZED_APPROVALS.get(expected_sha256)
    if authorized_ref is None:
        raise CommandError(
            'Approval file SHA-256 is not recorded in AUTHORIZED_APPROVALS. A matching hash proves the file '
            'is intact, not that the owner approved it; refusing.'
        )
    try:
        approval = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CommandError('Approval file is not valid JSON.') from None
    if not isinstance(approval, dict) or set(approval) != APPROVAL_KEYS:
        raise CommandError(f'Approval file must contain exactly these keys: {", ".join(sorted(APPROVAL_KEYS))}.')
    if approval['format'] != APPROVAL_FORMAT:
        raise CommandError('Approval file has an unknown format.')
    if not isinstance(approval['approval_ref'], str) or not approval['approval_ref'].strip():
        raise CommandError('Approval file has no approval_ref.')
    if approval['approval_ref'] != authorized_ref:
        raise CommandError('Approval file approval_ref differs from the reference recorded in AUTHORIZED_APPROVALS.')
    if approval['before_state_sha256'] != before_sha:
        raise CommandError('Approval file is bound to a different before-state.')
    if not isinstance(approval['preview_sha256'], str) or not _SHA256.fullmatch(approval['preview_sha256']):
        raise CommandError('Approval file has an invalid preview_sha256.')
    if approval['rules'] != [rule]:
        raise CommandError(f'Approval file does not approve exactly the selected rule {rule}.')
    if approval['classification_policy_sha256'] != manifest['classification_policy_sha256']:
        raise CommandError('Approval file is bound to a different classification policy.')
    if approval['wholesale_threshold_toman'] != manifest['wholesale_threshold_toman']:
        raise CommandError('Approval file is bound to a different wholesale threshold.')
    if approval['anomaly_wordpress_ids'] != sorted(APPROVED_ANOMALY_WORDPRESS_IDS):
        raise CommandError('Approval file lists different anomaly ids than the approved registry.')
    if approval['database_identity'] != manifest['database_identity']:
        raise CommandError('Approval file is bound to a different database.')
    if approval['imported_orders_fingerprint_sha256'] != manifest['imported_orders_fingerprint']['sha256']:
        raise CommandError('Approval file is bound to a different set of imported orders.')
    factors = approval['currency_factors']
    if not isinstance(factors, dict):
        raise CommandError('Approval file currency_factors must be an object.')
    for code, entry in factors.items():
        if (not isinstance(entry, dict) or set(entry) != {'toman_per_unit', 'evidence_ref'}
                or not isinstance(entry['evidence_ref'], str) or not entry['evidence_ref'].strip()):
            raise CommandError(f'Approval for currency {code!r} needs toman_per_unit and a non-empty evidence_ref.')
    return approval


def check_factor_approval(approval, targets):
    """Every currency in the batch needs an approved factor identical to the one in code."""
    factors = approval['currency_factors']
    for code in sorted({t['source_currency'] for t in targets}):
        entry = factors.get(code)
        if entry is None:
            raise CommandError(f'Conversion factor for {code} is not approved in the approval file.')
        try:
            approved = parse_amount(entry['toman_per_unit']) if isinstance(entry['toman_per_unit'], str) else None
        except MoneyConversionError:
            approved = None
        if approved is None:
            raise CommandError(f'Approved factor for {code} must be a decimal string.')
        if approved != TOMAN_PER_UNIT[code]:
            raise CommandError(f'Approved factor for {code} differs from the factor in code; refusing to apply.')


# ---------------------------------------------------------------- execution reports

RUN_FINAL_STATUSES = ('RUN_COMMITTED', 'RUN_COMMIT_UNKNOWN')


def load_execution_report(path, expected_sha256, before_rows, before_sha, approval_sha, approval, rule):
    """
    Validate a correction execution report and return (targets, final_status). The report must be
    byte-identical to the recorded hash, bound to the same approval, before-state and preview, and
    list exactly the approved batch with the before-state values. Rolled-back, no-op, truncated or
    edited reports are rejected.
    """
    path = Path(path)
    if not path.is_file():
        raise CommandError(f'Execution report not found: {path}')
    data = path.read_bytes()
    if sha256_bytes(data) != expected_sha256:
        raise CommandError('Execution report SHA-256 does not match --execution-report-sha256.')
    try:
        lines = list(csv.reader(io.StringIO(data.decode('utf-8'), newline='')))
    except (UnicodeDecodeError, csv.Error):
        raise CommandError('Execution report is not a valid UTF-8 CSV file.') from None
    if not lines or lines[0] != EXECUTION_COLUMNS:
        raise CommandError('Execution report header does not match the expected columns.')
    records = []
    for number, values in enumerate(lines[1:], start=2):
        if len(values) != len(EXECUTION_COLUMNS):
            raise CommandError(f'Execution report line {number}: expected {len(EXECUTION_COLUMNS)} columns.')
        records.append((number, dict(zip(EXECUTION_COLUMNS, values))))

    statuses = [r['status'] for _, r in records]
    count = next((i for i, s in enumerate(statuses) if s != 'INTENDED'), len(statuses))
    markers = statuses[count:]
    if markers == ['RUN_STARTED', 'RUN_ROLLED_BACK']:
        raise CommandError('The execution report records a rolled-back run; there is nothing to roll back.')
    if count == 0 or markers not in (['RUN_STARTED'], *(['RUN_STARTED', s] for s in RUN_FINAL_STATUSES)):
        raise CommandError('Execution report is incomplete or malformed: expected INTENDED rows, RUN_STARTED and at most one final status.')

    expected_common = {
        'approval_ref': approval['approval_ref'], 'approval_sha256': approval_sha,
        'before_state_sha256': before_sha, 'preview_sha256': approval['preview_sha256'], 'execution_report_sha256': '',
    }
    for number, record in records:
        if any(record[key] != value for key, value in expected_common.items()):
            raise CommandError(f'Execution report line {number}: bound to a different approval, before-state or preview.')

    by_pk = {row['order_id']: row for row in before_rows}
    batch = {row['order_id'] for row in before_rows if row['rule'] == rule and row['reason_code'] == CORRECTION_REASONS[rule]}
    targets, seen_pk, seen_wp = [], set(), set()
    for number, record in records[:count]:
        pk = _parse_int(record['order_id'], 'order_id', number, minimum=1, label='Execution report')
        wp_id = _parse_int(record['wordpress_id'], 'wordpress_id', number, minimum=1, label='Execution report')
        before = _parse_int(record['total_price_before'], 'total_price_before', number, label='Execution report')
        after = _parse_int(record['total_price_after'], 'total_price_after', number, label='Execution report')
        if pk in seen_pk or wp_id in seen_wp:
            raise CommandError(f'Execution report line {number}: duplicate order_id or wordpress_id.')
        seen_pk.add(pk)
        seen_wp.add(wp_id)
        row = by_pk.get(pk)
        if row is None or pk not in batch:
            raise CommandError(f'Execution report line {number}: order {pk} is not part of the approved {rule} batch.')
        recorded = (wp_id, record['rule'], record['reason_code'], record['source_currency'], record['factor'], before, after)
        expected = (row['wordpress_id'], row['rule'], row['reason_code'], row['source_currency'], row['factor'],
                    row['total_price_before'], row['proposed_after'])
        if recorded != expected:
            raise CommandError(f'Execution report line {number}: values differ from the before-state.')
        targets.append(row)
    if seen_pk != batch:
        raise CommandError('Execution report does not list the complete approved batch.')

    sums = (str(sum(t['total_price_before'] for t in targets)), str(sum(t['proposed_after'] for t in targets)))
    for number, record in records[count:]:
        if any(record[key] for key in ('order_id', 'wordpress_id', 'rule', 'reason_code', 'source_currency', 'factor')):
            raise CommandError(f'Execution report line {number}: a status row must not name an order.')
        if (record['total_price_before'], record['total_price_after']) != sums:
            raise CommandError(f'Execution report line {number}: status totals do not match the listed orders.')
    return targets, markers[-1]


def rollback_state(targets, current, payment_ids):
    """Split targets into (corrected, original, problems) by their current database values."""
    corrected, original, problems = [], [], []
    for target in targets:
        now = current.get(target['order_id'])
        if now is None:
            problems.append('DB_ORDER_MISSING')
        elif now[0] != target['wordpress_id']:
            problems.append('DB_WORDPRESS_ID_CHANGED')
        elif now[2] != target['is_paid_before']:
            problems.append('DB_IS_PAID_CHANGED')
        elif target['order_id'] in payment_ids:
            problems.append('DB_PAYMENT_PRESENT')
        elif now[1] == target['proposed_after']:
            corrected.append(target)
        elif now[1] == target['total_price_before']:
            original.append(target)
        else:
            problems.append('DB_TOTAL_CHANGED')
    return corrected, original, problems


# ---------------------------------------------------------------- command

class Command(BaseCommand):
    help = (
        'Imported order total correction: --snapshot writes the before-state; the default is a '
        'read-only preview; --apply and --rollback are disabled unless enabled in code and approved.'
    )

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--snapshot', action='store_true', help='Write the before-state and its manifest (read-only).')
        mode.add_argument('--apply', action='store_true', help='Apply one approved rule batch (disabled in this build).')
        mode.add_argument('--rollback', action='store_true', help='Restore one committed batch from its execution report (disabled in this build).')
        parser.add_argument('--export', help='WXR export (snapshot mode).')
        parser.add_argument('--before-state', required=True, help='Before-state CSV; its manifest is <path>.manifest.json.')
        parser.add_argument('--before-state-sha256', help='Recorded SHA-256 of the before-state (preview, apply, rollback).')
        parser.add_argument('--preview', help='Preview CSV to write (preview mode); a .summary.json and .approval-request.json are written next to it.')
        parser.add_argument('--rule', action='append', choices=CORRECTABLE_RULES, help='Rule batch(es) to propose; apply and rollback take exactly one.')
        parser.add_argument('--approval-file', help='Approval JSON (apply, rollback).')
        parser.add_argument('--approval-sha256', help='SHA-256 of the approval file (apply, rollback).')
        parser.add_argument('--execution-report', help='Execution report CSV: written by apply, read by rollback.')
        parser.add_argument('--execution-report-sha256', help='Recorded SHA-256 of the execution report (rollback).')
        parser.add_argument('--rollback-report', help='Rollback report CSV to write (rollback).')
        parser.add_argument('--wholesale-threshold', default=str(DEFAULT_WHOLESALE_THRESHOLD))
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS)

    def handle(self, *args, **options):
        if options['snapshot']:
            return self._snapshot(options)
        if options['apply']:
            return self._apply(options)
        if options['rollback']:
            return self._rollback(options)
        return self._preview(options)

    # -- snapshot

    def _snapshot(self, options):
        if not options['export']:
            raise CommandError('--snapshot requires --export.')
        try:
            threshold = parse_amount(options['wholesale_threshold'])
        except MoneyConversionError as exc:
            raise CommandError(f'Invalid --wholesale-threshold: {exc}') from None
        path = Path(options['before_state'])
        outputs = Outputs(path, f'{path}.manifest.json').reserve()
        try:
            orders, refunds = load_export(options['export'])
            using = options['database']
            with read_only(using):
                identity = database_identity(using)
                current = _current_orders(using)
                payment_ids, payment_table = _payment_order_ids(using)
            rows = build_before_state(orders, refunds, current, payment_ids, threshold)
            data = _csv_bytes(BEFORE_STATE_COLUMNS, rows)
            digest = sha256_bytes(data)
            policy = classification_policy()
            manifest = {
                'format': BEFORE_STATE_FORMAT,
                'created_at': timezone.now().isoformat(),
                'before_state_file': path.name,
                'before_state_sha256': digest,
                'export_sha256': sha256_file(options['export']),
                'export_size_bytes': os.path.getsize(options['export']),
                'database_vendor': connections[using].vendor,
                'database_identity': identity,
                'payment_table_present': payment_table,
                'wholesale_threshold_toman': str(threshold),
                'wholesale_threshold_reviewed': threshold == REVIEWED_WHOLESALE_THRESHOLD,
                'classification_policy': policy,
                'classification_policy_sha256': policy_sha256(policy),
                'conversion_factors': _factor_table(),
                'rows': len(rows),
                'rules': _rule_totals(rows),
                'imported_orders_fingerprint': imported_fingerprint(current),
                'notice': NOTICE,
            }
            outputs.write(path, data)
            outputs.write(f'{path}.manifest.json', _json_bytes(manifest))
        except BaseException:
            outputs.discard()
            raise
        outputs.close()
        self.stdout.write('== Before-state snapshot (read-only; no data was changed) ==')
        self.stdout.write(f'NOTICE: {NOTICE}')
        for rule, info in manifest['rules'].items():
            self.stdout.write(
                f"  rule {rule}: orders={info['orders']} before_sum={info['total_price_before']} "
                f"proposed={info['proposed']} proposed_after_sum={info['proposed_after']}"
            )
        self.stdout.write(f'rows={len(rows)}')
        self.stdout.write(f"classification_policy_sha256={manifest['classification_policy_sha256']}")
        self.stdout.write(f'before_state_sha256={digest}')
        self.stdout.write(f'Before-state written to {path} (manifest: {path}.manifest.json)')

    # -- preview

    def _load_inputs(self, options):
        before_sha = _normalize_sha256(options['before_state_sha256'], '--before-state-sha256')
        rows, manifest, before_sha = load_before_state(options['before_state'], before_sha)
        return rows, manifest, before_sha

    def _read_current(self, using, expected_identity=None):
        """Orders and payments from one read-only snapshot; with an identity, schema and target are verified first."""
        with read_only(using):
            if expected_identity is not None:
                check_schema(using)
                check_identity(expected_identity, database_identity(using))
            current = _current_orders(using)
            payment_ids, _ = _payment_order_ids(using)
        return current, payment_ids

    def _preview(self, options):
        if not options['preview']:
            raise CommandError('Preview mode requires --preview (a new CSV path).')
        for option in ('approval_file', 'execution_report', 'execution_report_sha256', 'rollback_report'):
            if options[option]:
                raise CommandError('--approval-file, --execution-report and --rollback-report are only valid with --apply or --rollback.')
        preview_path = Path(options['preview'])
        summary_path = Path(f'{preview_path}.summary.json')
        request_path = Path(f'{preview_path}.approval-request.json')
        outputs = Outputs(preview_path, summary_path, request_path).reserve()
        try:
            before_rows, manifest, before_sha = self._load_inputs(options)
            using = options['database']
            with read_only(using):
                identity = database_identity(using)
                current = _current_orders(using)
                payment_ids, _ = _payment_order_ids(using)
            rules = sorted(set(options['rule'] or []))
            rows = build_preview(before_rows, current, payment_ids, rules)
            data = _csv_bytes(PREVIEW_COLUMNS, rows)
            preview_sha = sha256_bytes(data)
            summary = preview_summary(rows, before_sha, manifest, current, rules, identity)
            summary['preview_sha256'] = preview_sha
            if len(rules) == 1:
                request = approval_request(summary, manifest, preview_sha)
            else:
                request = {'format': APPROVAL_FORMAT, 'note': 'An approval covers exactly one rule; preview with a single --rule.'}
            outputs.write(preview_path, data)
            outputs.write(summary_path, _json_bytes(summary))
            outputs.write(request_path, _json_bytes(request))
        except BaseException:
            outputs.discard()
            raise
        outputs.close()
        for line in summary_lines(summary, preview_sha):
            self.stdout.write(line)
        self.stdout.write(f'Preview written to {preview_path} (summary: {summary_path}, approval request: {request_path})')

    # -- apply and rollback: shared guards

    def _require(self, options, names, mode):
        if not EXECUTION_ENABLED:
            raise CommandError(
                'Execution is disabled in this build (EXECUTION_ENABLED is False). No data was changed. '
                'Enabling it requires a reviewed code change after owner approval, a verified backup and '
                'confirmed currency rules.'
            )
        rules = options['rule'] or []
        if len(rules) != 1:
            raise CommandError(f'--{mode} requires exactly one --rule.')
        for option in names:
            if not options[option]:
                raise CommandError(f"--{mode} requires --{option.replace('_', '-')}.")
        if options['preview']:
            raise CommandError(f'--preview is not used with --{mode}.')
        return rules[0]

    def _authorised_inputs(self, options, rule, approval_sha):
        before_rows, manifest, before_sha = self._load_inputs(options)
        approval = load_approval(options['approval_file'], approval_sha, before_sha, manifest, rule)
        check_reviewed_threshold(manifest)
        check_anomaly_registry(before_rows)
        return before_rows, manifest, before_sha, approval

    def _run_write(self, using, identity, body):
        """Return (outcome, exception). A failure after the body finished happened at commit: outcome unknown."""
        progress = {'body_done': False}
        try:
            with write_transaction(using, identity):
                body()
                progress['body_done'] = True
        except BaseException as exc:
            return ('COMMIT_UNKNOWN' if progress['body_done'] else 'ROLLED_BACK'), exc
        return 'COMMITTED', None

    def _finish(self, outputs, path, prefix, outcome, exc, targets, common, label, noun):
        self._write_marker(outputs, path, f'{prefix}_{outcome}', targets, common)
        outputs.close()
        report_sha = sha256_file(path)
        self.stdout.write(f'{label}_report_sha256={report_sha}')
        if exc is None:
            return report_sha
        if outcome == 'COMMIT_UNKNOWN':
            if not isinstance(exc, Exception):
                raise exc
            raise CommandError(
                f'{noun} commit outcome unknown ({_describe(exc)}). Do not retry blindly: run a preview to see '
                f'which values the orders hold; the report ends with {prefix}_COMMIT_UNKNOWN.'
            ) from None
        if isinstance(exc, CommandError) or not isinstance(exc, Exception):
            raise exc
        raise CommandError(f'{noun} rolled back ({_describe(exc)}); no data was changed.') from None

    # -- apply

    def _apply(self, options):
        rule = self._require(options, ('approval_file', 'approval_sha256', 'execution_report', 'before_state_sha256'), 'apply')
        if options['rollback_report'] or options['execution_report_sha256']:
            raise CommandError('--rollback-report and --execution-report-sha256 are only valid with --rollback.')
        approval_sha = _normalize_sha256(options['approval_sha256'], '--approval-sha256')
        report_path = Path(options['execution_report'])
        outputs = Outputs(report_path).reserve()
        try:
            before_rows, manifest, before_sha, approval = self._authorised_inputs(options, rule, approval_sha)
            using = options['database']
            current, payment_ids = self._read_current(using, manifest['database_identity'])
            rows = build_preview(before_rows, current, payment_ids, [rule])
            preview_sha = sha256_bytes(_csv_bytes(PREVIEW_COLUMNS, rows))
            targets = [r for r in rows if r['category'] == PROPOSED]
            applied = [r for r in rows if r['category'] == ALREADY_APPLIED and r['rule'] == rule]
            conflicts = [r for r in rows if r['category'] == CONFLICT]
            stale = [r for r in rows if r['category'] == ALREADY_APPLIED and r['rule'] != rule]
            common = {
                'approval_ref': approval['approval_ref'], 'approval_sha256': approval_sha,
                'before_state_sha256': before_sha, 'preview_sha256': preview_sha,
            }
            if conflicts:
                reasons = ', '.join(f'{k}={v}' for k, v in sorted(Counter(r['reason_code'] for r in conflicts).items()))
                raise CommandError(
                    f'{len(conflicts)} rows changed since the before-state ({reasons}); take a fresh snapshot, '
                    'preview and approval.'
                )
            if stale:
                raise CommandError(
                    f'{len(stale)} rows of other batches were corrected after this before-state; take a fresh '
                    'snapshot, preview and approval.'
                )
            if targets and applied:
                raise CommandError(f'{rule}: {len(targets)} rows pending and {len(applied)} already applied; refusing a mixed state.')
            if not targets and not applied:
                raise CommandError(f'{rule}: no proposed corrections.')
            expected_fp = _fingerprint_with(before_rows, {r['order_id'] for r in applied})
            if imported_fingerprint(current) != expected_fp:
                raise CommandError('Imported orders differ from the before-state fingerprint; take a fresh snapshot.')
            assert_batch_eligible(before_rows, [r['order_id'] for r in targets or applied], rule)
            if applied:
                self._write_execution(outputs, report_path, applied, 'ALREADY_APPLIED', common, marker='RUN_NOOP_ALREADY_APPLIED')
                outputs.close()
                self.stdout.write(f'Nothing to apply: all {len(applied)} {rule} corrections are already applied. No data was changed.')
                return
            if preview_sha != approval['preview_sha256']:
                raise CommandError('The regenerated preview does not match the approved preview_sha256; the data or inputs changed.')
            check_factor_approval(approval, targets)
        except BaseException:
            outputs.discard()
            raise

        self._write_execution(outputs, report_path, targets, 'INTENDED', common, marker='RUN_STARTED')
        outcome, exc = self._run_write(using, manifest['database_identity'], lambda: self._execute(using, targets))
        self._finish(outputs, report_path, 'RUN', outcome, exc, targets, common, 'execution', 'Correction')
        self.stdout.write(f'{rule}: {len(targets)} corrections committed. Execution report: {report_path}')

    def _execute(self, using, targets):
        from orders.models import Order

        ids = [t['order_id'] for t in targets]
        self._lock_rows(using, ids)
        self._check_no_payments(using, ids)
        for target in targets:
            if self._compare_and_set(using, target) != 1:
                raise CommandError(
                    f"Order {target['order_id']} changed during the run; correction rolled back, no data was changed."
                )
        if self._sum_totals(using, Order, ids) != sum(t['proposed_after'] for t in targets):
            raise CommandError('Post-update sum differs from the preview; correction rolled back.')

    @staticmethod
    def _compare_and_set(using, target):
        from orders.models import Order

        return Order.objects.using(using).filter(
            pk=target['order_id'],
            wordpress_id=target['wordpress_id'],
            total_price=target['total_price_before'],
            is_paid=target['is_paid_before'],
        ).update(total_price=target['proposed_after'])

    # -- rollback

    def _rollback(self, options):
        rule = self._require(options, (
            'approval_file', 'approval_sha256', 'execution_report', 'execution_report_sha256',
            'rollback_report', 'before_state_sha256',
        ), 'rollback')
        approval_sha = _normalize_sha256(options['approval_sha256'], '--approval-sha256')
        execution_sha = _normalize_sha256(options['execution_report_sha256'], '--execution-report-sha256')
        report_path = Path(options['rollback_report'])
        outputs = Outputs(report_path).reserve()
        try:
            before_rows, manifest, before_sha, approval = self._authorised_inputs(options, rule, approval_sha)
            targets, run_status = load_execution_report(
                options['execution_report'], execution_sha, before_rows, before_sha, approval_sha, approval, rule,
            )
            using = options['database']
            current, payment_ids = self._read_current(using, manifest['database_identity'])
            corrected, original, problems = rollback_state(targets, current, payment_ids)
            common = {
                'approval_ref': approval['approval_ref'], 'approval_sha256': approval_sha,
                'before_state_sha256': before_sha, 'preview_sha256': approval['preview_sha256'],
                'execution_report_sha256': execution_sha,
            }
            if problems:
                reasons = ', '.join(f'{k}={v}' for k, v in sorted(Counter(problems).items()))
                raise CommandError(f'{len(problems)} orders do not hold their corrected or original value ({reasons}); refusing the rollback.')
            if corrected and original:
                raise CommandError(
                    f'{len(corrected)} orders hold the corrected value and {len(original)} the original; refusing a '
                    'mixed state. Restore from the verified backup instead.'
                )
        except BaseException:
            outputs.discard()
            raise

        if original:
            self._write_execution(outputs, report_path, original, 'ALREADY_RESTORED', common, marker='ROLLBACK_NOOP_ALREADY_RESTORED')
            outputs.close()
            self.stdout.write(f'Nothing to roll back ({run_status}): all {len(original)} {rule} orders hold their original value. No data was changed.')
            return
        self._write_execution(outputs, report_path, corrected, 'ROLLBACK_INTENDED', common, marker='ROLLBACK_STARTED')
        outcome, exc = self._run_write(using, manifest['database_identity'], lambda: self._restore(using, corrected))
        self._finish(outputs, report_path, 'ROLLBACK', outcome, exc, corrected, common, 'rollback', 'Rollback')
        self.stdout.write(f'{rule}: {len(corrected)} orders restored to their original value. Rollback report: {report_path}')

    def _restore(self, using, targets):
        from orders.models import Order

        ids = [t['order_id'] for t in targets]
        self._lock_rows(using, ids)
        self._check_no_payments(using, ids)
        for target in targets:
            if self._restore_one(using, target) != 1:
                raise CommandError(f"Order {target['order_id']} changed during the rollback; rolled back, no data was changed.")
        if self._sum_totals(using, Order, ids) != sum(t['total_price_before'] for t in targets):
            raise CommandError('Post-rollback sum differs from the before-state; rolled back.')

    @staticmethod
    def _restore_one(using, target):
        from orders.models import Order

        return Order.objects.using(using).filter(
            pk=target['order_id'],
            wordpress_id=target['wordpress_id'],
            total_price=target['proposed_after'],
            is_paid=target['is_paid_before'],
        ).update(total_price=target['total_price_before'])

    # -- write helpers (run inside write_transaction)

    @staticmethod
    def _lock_rows(using, ids):
        from orders.models import Order

        locked = 0
        try:
            for chunk in _chunks(ids):
                locked += len(Order.objects.using(using).select_for_update(nowait=True)
                              .filter(pk__in=chunk).values_list('pk', flat=True))
        except OperationalError as exc:
            code = getattr(exc.__cause__, 'pgcode', None)
            if code == '55P03':
                raise CommandError('A target order is locked by another transaction (NOWAIT); nothing was changed.') from None
            if code == '40001':
                raise CommandError('A target order was changed by a concurrent transaction (serialization failure); nothing was changed.') from None
            raise
        if locked != len(ids):
            raise CommandError(f'{len(ids) - locked} target orders no longer exist; nothing was changed.')

    @staticmethod
    def _check_no_payments(using, ids):
        from payment.models import Payment

        if Payment._meta.db_table not in connections[using].introspection.table_names():
            raise CommandError('The payment table is missing; refusing to write without the payment re-check.')
        for chunk in _chunks(ids):
            if Payment.objects.using(using).filter(order_id__in=chunk).exists():
                raise CommandError('A payment record exists for a target order; rolled back, no data was changed.')

    @staticmethod
    def _sum_totals(using, model, ids):
        return sum(
            model.objects.using(using).filter(pk__in=chunk).aggregate(total=Sum('total_price'))['total'] or 0
            for chunk in _chunks(ids)
        )

    @staticmethod
    def _execution_rows(targets, status, common):
        return [{
            'status': status, 'order_id': t['order_id'], 'wordpress_id': t['wordpress_id'], 'rule': t['rule'],
            'reason_code': t['reason_code'], 'source_currency': t['source_currency'], 'factor': t['factor'],
            'total_price_before': t['total_price_before'], 'total_price_after': t['proposed_after'], **common,
        } for t in targets]

    def _write_execution(self, outputs, path, targets, status, common, marker=None):
        outputs.write(path, _csv_bytes(EXECUTION_COLUMNS, self._execution_rows(targets, status, common)))
        if marker:
            self._write_marker(outputs, path, marker, targets, common)

    @staticmethod
    def _write_marker(outputs, path, status, targets, common):
        row = {
            'status': status,
            'total_price_before': sum(t['total_price_before'] for t in targets),
            'total_price_after': sum(t['proposed_after'] for t in targets),
            **common,
        }
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator='\n').writerow(['' if row.get(c) is None else row[c] for c in EXECUTION_COLUMNS])
        outputs.write(path, buffer.getvalue().encode('utf-8'))
