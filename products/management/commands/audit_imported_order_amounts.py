"""
Read-only reconciliation of imported WooCommerce order totals against the WXR export.

Never writes to the database: it reads (wordpress_id, total_price) of imported orders and
compares them with the export's `_order_total` converted by `_order_currency`. Only ids, codes
and amounts are read from the export; billing/customer fields are never parsed.

Zero-total policy: a zero source total converts to zero in every currency. A stored zero is
MATCH (flagged ZERO_TOTAL); a non-zero stored value is MISMATCH. RAW_IRR / RAW_IRHT are only
used when the source amount is non-zero, so a zero is never reported as a unit error.
"""

import csv
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections, transaction

from core.money import (
    MoneyConversionError,
    normalize_currency,
    parse_amount,
    woo_amount_to_toman,
)

NS = {'wp': 'http://wordpress.org/export/1.2/'}

MATCH = 'MATCH'
RAW_IRR = 'RAW_IRR'
RAW_IRHT = 'RAW_IRHT'
MISMATCH = 'MISMATCH'
MISSING_IN_DB = 'MISSING_IN_DB'
MISSING_IN_EXPORT = 'MISSING_IN_EXPORT'
DUPLICATE_IN_EXPORT = 'DUPLICATE_IN_EXPORT'
DUPLICATE_IN_DB = 'DUPLICATE_IN_DB'
SOURCE_INVALID = 'SOURCE_INVALID'
NOT_COMPARED = 'NOT_COMPARED'
NOT_APPLICABLE = 'NOT_APPLICABLE'

FLAG_ZERO_TOTAL = 'ZERO_TOTAL'
FLAG_REFUNDED_STATUS = 'REFUNDED_STATUS'
FLAG_HAS_REFUND_RECORD = 'HAS_REFUND_RECORD'
FLAG_WHOLESALE_SIZED = 'WHOLESALE_SIZED'
FLAG_CANCELLED_SEP_ANOMALY = 'CANCELLED_SEP_ANOMALY'
FLAG_IRR_NOT_DIVISIBLE_BY_10 = 'IRR_NOT_DIVISIBLE_BY_10'
FLAG_REFUND_WITHOUT_PARENT = 'REFUND_WITHOUT_PARENT'
FLAG_INVALID_AMOUNT = 'INVALID_SOURCE_AMOUNT'
FLAG_INVALID_CURRENCY = 'INVALID_SOURCE_CURRENCY'
FLAG_INVALID_ID = 'INVALID_SOURCE_ID'

# Orders above this (in Toman) are flagged for review; P0-2 audit: 200M Rial / 20,000 thousand Toman.
DEFAULT_WHOLESALE_THRESHOLD = Decimal('20000000')
# IRHT totals above this many source units are large. Fixed in code and measured in the source unit,
# so neither --wholesale-threshold nor the unapproved IRHT factor can move an order across it.
LARGE_IRHT_SOURCE_UNITS = Decimal('20000')

CSV_COLUMNS = [
    'record_type', 'wordpress_id', 'parent_wordpress_id', 'source_status', 'source_currency',
    'source_amount', 'expected_toman', 'stored_total', 'discrepancy', 'classification', 'flags', 'note',
]

ASSUMPTIONS = [
    'Conversion factors (IRR /10, IRT x1, IRHR x100, IRHT x1000) are provisional; the original '
    "store's currency settings, including IRHT = thousand Toman, are not independently verified.",
    'The export has no order line items; only order totals are reconciled.',
    'Shipping, discount and refund amounts are not imported into Django and are not compared.',
    'RAW_* assumes the importer stored the source total truncated to an integer (int(float(...))).',
    'WHOLESALE_SIZED and CANCELLED_SEP_ANOMALY are review heuristics, not classifications. '
    'CANCELLED_SEP_ANOMALY uses a fixed IRHT size limit and does not depend on --wholesale-threshold.',
    'Order status breakdowns use the export status; the database status is not read.',
]


@dataclass
class SourceOrder:
    wordpress_id: str
    status: str = ''
    currency: str = ''
    total: str = ''
    payment_method: str = ''


@dataclass
class SourceRefund:
    wordpress_id: str
    parent_id: str = ''
    currency: str = ''
    amount: str = ''


@dataclass
class Report:
    rows: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def _text(el):
    return (el.text or '').strip() if el is not None else ''


def load_export(path):
    """Parse shop_order / shop_order_refund items. Raises CommandError if unusable."""
    path = Path(path)
    if not path.is_file():
        raise CommandError(f'Source export not found: {path}. Reconciliation cannot be completed.')
    orders, refunds = [], []
    try:
        for _, elem in ET.iterparse(path, events=('end',)):
            if elem.tag != 'item':
                continue
            post_type = _text(elem.find('wp:post_type', NS))
            if post_type in ('shop_order', 'shop_order_refund'):
                metas = {
                    _text(m.find('wp:meta_key', NS)): _text(m.find('wp:meta_value', NS))
                    for m in elem.findall('wp:postmeta', NS)
                    if _text(m.find('wp:meta_key', NS)) in (
                        '_order_currency', '_order_total', '_payment_method', '_refund_amount',
                    )
                }
                post_id = _text(elem.find('wp:post_id', NS))
                if post_type == 'shop_order':
                    orders.append(SourceOrder(
                        wordpress_id=post_id,
                        status=_text(elem.find('wp:status', NS)),
                        currency=metas.get('_order_currency', ''),
                        total=metas.get('_order_total', ''),
                        payment_method=metas.get('_payment_method', ''),
                    ))
                else:
                    refunds.append(SourceRefund(
                        wordpress_id=post_id,
                        parent_id=_text(elem.find('wp:post_parent', NS)),
                        currency=metas.get('_order_currency', ''),
                        amount=metas.get('_refund_amount', ''),
                    ))
            elem.clear()
    except ET.ParseError as exc:
        raise CommandError(f'Source export is not valid XML ({exc}). Reconciliation cannot be completed.')
    if not orders:
        raise CommandError(f'Source export has no shop_order records: {path}. Reconciliation cannot be completed.')
    return orders, refunds


def _wp_id(value):
    text = str(value).strip()
    return int(text) if text.isascii() and text.isdigit() and int(text) > 0 else None


def _convert(raw, currency):
    """Return (amount, code, expected_toman, flags) with None for anything that cannot be derived."""
    flags = []
    amount = code = expected = None
    try:
        amount = parse_amount(raw)
    except MoneyConversionError:
        flags.append(FLAG_INVALID_AMOUNT)
    try:
        code = normalize_currency(currency)
    except MoneyConversionError:
        flags.append(FLAG_INVALID_CURRENCY)
    if amount is not None and code is not None:
        expected = woo_amount_to_toman(amount, code)
    return amount, code, expected, flags


def _row(**values):
    row = dict.fromkeys(CSV_COLUMNS, '')
    row.update(values)
    return row


def reconcile(orders, refunds, db_rows, wholesale_threshold=DEFAULT_WHOLESALE_THRESHOLD):
    """
    orders/refunds: parsed export records. db_rows: iterable of (wordpress_id, total_price) for
    imported orders, or None when the database was not inspected.
    """
    wholesale_threshold = Decimal(wholesale_threshold)
    rows = []
    order_ids = Counter(_wp_id(o.wordpress_id) for o in orders)
    refund_parents = Counter(_wp_id(r.parent_id) for r in refunds)

    db_inspected = db_rows is not None
    db_rows = list(db_rows or [])
    db_counts = Counter(wp_id for wp_id, _ in db_rows)
    stored_by_id = {wp_id: int(total) for wp_id, total in db_rows if db_counts[wp_id] == 1}

    currency_totals = defaultdict(lambda: {
        'orders': 0, 'source_amount': Decimal(0), 'expected_toman': Decimal(0),
        'compared': 0, 'stored_total': Decimal(0), 'discrepancy': Decimal(0),
    })
    status_counts = Counter()

    for order in orders:
        wp_id = _wp_id(order.wordpress_id)
        amount, code, expected, flags = _convert(order.total, order.currency)
        currency_key = code or (order.currency or '(missing)')
        bucket = currency_totals[currency_key]
        bucket['orders'] += 1
        status_counts[order.status or '(missing)'] += 1
        if amount is not None and code is not None:
            bucket['source_amount'] += amount
            bucket['expected_toman'] += expected

        if amount is not None and amount == 0:
            flags.append(FLAG_ZERO_TOTAL)
        if order.status == 'wc-refunded':
            flags.append(FLAG_REFUNDED_STATUS)
        if wp_id is not None and refund_parents[wp_id]:
            flags.append(FLAG_HAS_REFUND_RECORD)
        if expected is not None and expected > wholesale_threshold:
            flags.append(FLAG_WHOLESALE_SIZED)
        if (order.status == 'wc-cancelled' and code == 'IRHT' and amount is not None
                and amount > LARGE_IRHT_SOURCE_UNITS and 'sep' in order.payment_method.lower()):
            flags.append(FLAG_CANCELLED_SEP_ANOMALY)
        if code == 'IRR' and amount is not None and amount % 10:
            flags.append(FLAG_IRR_NOT_DIVISIBLE_BY_10)
        if wp_id is None:
            flags.append(FLAG_INVALID_ID)

        stored = stored_by_id.get(wp_id)
        note = ''
        if wp_id is None:
            classification, note = SOURCE_INVALID, 'missing or non-numeric post id'
        elif order_ids[wp_id] > 1:
            classification, note = DUPLICATE_IN_EXPORT, 'wordpress_id appears more than once in the export'
        elif not db_inspected:
            classification = NOT_COMPARED
        elif db_counts[wp_id] > 1:
            classification, note = DUPLICATE_IN_DB, 'wordpress_id appears more than once in the database'
        elif wp_id not in stored_by_id:
            classification = MISSING_IN_DB
        elif expected is None:
            classification, note = SOURCE_INVALID, 'source amount or currency cannot be converted'
        else:
            as_imported = int(amount.to_integral_value(rounding=ROUND_DOWN))
            if stored == expected:
                classification = MATCH
            elif as_imported and stored == as_imported and code == 'IRR':
                classification = RAW_IRR
            elif as_imported and stored == as_imported and code == 'IRHT':
                classification = RAW_IRHT
            else:
                classification = MISMATCH

        compared = classification in (MATCH, RAW_IRR, RAW_IRHT, MISMATCH)
        discrepancy = stored - expected if compared else None
        if compared:
            bucket['compared'] += 1
            bucket['stored_total'] += stored
            bucket['discrepancy'] += discrepancy
        rows.append(_row(
            record_type='order',
            wordpress_id=wp_id if wp_id is not None else order.wordpress_id,
            source_status=order.status,
            source_currency=order.currency,
            source_amount=order.total,
            expected_toman='' if expected is None else expected,
            stored_total='' if stored is None or classification == DUPLICATE_IN_EXPORT else stored,
            discrepancy='' if discrepancy is None else discrepancy,
            classification=classification,
            flags=';'.join(sorted(flags)),
            note=note,
        ))

    export_ids = {wp_id for wp_id in order_ids if wp_id is not None}
    if db_inspected:
        for wp_id in sorted(db_counts):
            if wp_id in export_ids:
                continue
            for _, total in (r for r in db_rows if r[0] == wp_id):
                rows.append(_row(
                    record_type='order', wordpress_id=wp_id, stored_total=int(total),
                    classification=DUPLICATE_IN_DB if db_counts[wp_id] > 1 else MISSING_IN_EXPORT,
                ))

    orphan_refunds = 0
    for refund in refunds:
        parent = _wp_id(refund.parent_id)
        if parent is not None and parent in export_ids:
            continue
        orphan_refunds += 1
        _, _, expected, flags = _convert(refund.amount, refund.currency)
        rows.append(_row(
            record_type='refund',
            wordpress_id=refund.wordpress_id,
            parent_wordpress_id=refund.parent_id,
            source_currency=refund.currency,
            source_amount=refund.amount,
            expected_toman='' if expected is None else expected,
            classification=NOT_APPLICABLE,
            flags=';'.join(sorted(flags + [FLAG_REFUND_WITHOUT_PARENT])),
            note='refund records are not imported into Django',
        ))

    rows.sort(key=lambda r: (r['record_type'], str(r['wordpress_id']).zfill(20), r['classification'], str(r)))

    flag_counts = Counter(flag for r in rows for flag in r['flags'].split(';') if flag)
    compared_rows = [r for r in rows if r['discrepancy'] != '']
    summary = {
        'source': {
            'export_orders': len(orders),
            'export_refunds': len(refunds),
            'refunds_without_parent': orphan_refunds,
            'duplicate_ids_in_export': sum(1 for wp_id, n in order_ids.items() if wp_id is not None and n > 1),
            'orders_by_currency': {k: currency_totals[k] for k in sorted(currency_totals)},
            'orders_by_status': dict(sorted(status_counts.items())),
            'flags': dict(sorted(flag_counts.items())),
        },
        'database': {
            'inspected': db_inspected,
            'imported_orders': len(db_rows) if db_inspected else None,
            'duplicate_ids_in_db': sum(1 for n in db_counts.values() if n > 1) if db_inspected else None,
        },
        'reconciliation': {
            'by_classification': dict(sorted(Counter(r['classification'] for r in rows).items())),
            'expected_toman': sum((Decimal(r['expected_toman']) for r in compared_rows), Decimal(0)),
            'stored_total': sum((Decimal(r['stored_total']) for r in compared_rows), Decimal(0)),
            'discrepancy': sum((Decimal(r['discrepancy']) for r in compared_rows), Decimal(0)),
        },
        'wholesale_threshold_toman': wholesale_threshold,
        'assumptions': list(ASSUMPTIONS) + ([] if db_inspected else [
            'Database not inspected (--skip-db): no order has been compared.',
        ]),
    }
    return Report(rows=rows, summary=summary)


_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def _csv_safe(value):
    """Numbers are written as-is; text that a spreadsheet could execute as a formula is neutralised."""
    if isinstance(value, (int, Decimal)):
        return str(value)
    text = str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def write_csv(report, handle):
    writer = csv.writer(handle)
    writer.writerow(CSV_COLUMNS)
    for row in report.rows:
        writer.writerow([_csv_safe(row[column]) for column in CSV_COLUMNS])


def summary_lines(report):
    s = report.summary
    lines = ['== Source export (WXR) findings ==']
    lines.append(f"orders={s['source']['export_orders']} refunds={s['source']['export_refunds']} "
                 f"refunds_without_parent={s['source']['refunds_without_parent']} "
                 f"duplicate_ids={s['source']['duplicate_ids_in_export']}")
    for code, b in s['source']['orders_by_currency'].items():
        lines.append(f"  currency {code}: orders={b['orders']} source_sum={b['source_amount']} "
                     f"expected_toman={b['expected_toman']} compared={b['compared']} "
                     f"stored_toman={b['stored_total']} discrepancy={b['discrepancy']}")
    for status, n in s['source']['orders_by_status'].items():
        lines.append(f'  status {status}: {n}')
    for flag, n in s['source']['flags'].items():
        lines.append(f'  flag {flag}: {n}')
    lines.append('== Database observations ==')
    if s['database']['inspected']:
        lines.append(f"imported_orders={s['database']['imported_orders']} "
                     f"duplicate_ids={s['database']['duplicate_ids_in_db']}")
    else:
        lines.append('not inspected')
    lines.append('== Reconciliation ==')
    for name, n in s['reconciliation']['by_classification'].items():
        lines.append(f'  {name}: {n}')
    lines.append(f"compared expected_toman={s['reconciliation']['expected_toman']} "
                 f"stored={s['reconciliation']['stored_total']} "
                 f"discrepancy={s['reconciliation']['discrepancy']}")
    lines.append(f"wholesale threshold (Toman): {s['wholesale_threshold_toman']}")
    lines.append('== Assumptions / unavailable data ==')
    lines.extend(f'  - {a}' for a in s['assumptions'])
    return lines


def read_imported_totals(using=DEFAULT_DB_ALIAS):
    """SELECT only. On PostgreSQL the read runs inside a READ ONLY transaction when possible."""
    from orders.models import Order

    query = (
        Order.objects.using(using)
        .filter(wordpress_id__isnull=False)
        .order_by('wordpress_id')
        .values_list('wordpress_id', 'total_price')
    )
    connection = connections[using]
    if connection.vendor == 'postgresql' and not connection.in_atomic_block:
        with transaction.atomic(using=using):
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
            return list(query)
    return list(query)


class Command(BaseCommand):
    help = 'Read-only: compare imported order totals with the WooCommerce WXR export (no data is changed).'

    def add_arguments(self, parser):
        parser.add_argument('--export', required=True, help='Path to the WXR file containing shop_order items.')
        parser.add_argument('--output', help='Write the per-order report to this CSV file.')
        parser.add_argument('--overwrite', action='store_true', help='Allow replacing an existing --output file.')
        parser.add_argument('--skip-db', action='store_true', help='Analyse the export only; do not read the database.')
        parser.add_argument(
            '--wholesale-threshold', default=str(DEFAULT_WHOLESALE_THRESHOLD),
            help='Flag orders whose converted total exceeds this many Toman (default: %(default)s).',
        )
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS)

    def handle(self, *args, **options):
        try:
            threshold = parse_amount(options['wholesale_threshold'])
        except MoneyConversionError as exc:
            raise CommandError(f'Invalid --wholesale-threshold: {exc}')
        output = Path(options['output']) if options['output'] else None
        if output and output.exists() and not options['overwrite']:
            raise CommandError(f'{output} already exists; pass --overwrite to replace it.')

        orders, refunds = load_export(options['export'])
        db_rows = None if options['skip_db'] else read_imported_totals(options['database'])
        report = reconcile(orders, refunds, db_rows, wholesale_threshold=threshold)

        if output:
            with output.open('w', encoding='utf-8', newline='') as handle:
                write_csv(report, handle)
        for line in summary_lines(report):
            self.stdout.write(line)
        if output:
            self.stdout.write(f'Report written to {output}')
