import csv
import hashlib
import io
import json
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from orders.factories import OrderFactory
from orders.models import Order
from payment import services
from payment.models import Payment
from products.management.commands import correct_imported_order_amounts as correction
from products.management.commands.audit_imported_order_amounts import (
    DUPLICATE_IN_EXPORT,
    FLAG_CANCELLED_SEP_ANOMALY,
    FLAG_HAS_REFUND_RECORD,
    FLAG_WHOLESALE_SIZED,
    FLAG_ZERO_TOTAL,
    MATCH,
    MISMATCH,
    MISSING_IN_EXPORT,
    RAW_IRHT,
    RAW_IRR,
    SOURCE_INVALID,
)
from products.tests_order_amount_audit import PII, _order_xml, _refund_xml, _wxr

COMMAND = 'correct_imported_order_amounts'
WRITE_SQL = ('INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'DROP', 'ALTER')


def classify(classification, status, currency, amount, stored, flags=(), has_payment=False, wordpress_id=None):
    amount = None if amount is None else Decimal(amount)
    return correction.classify(classification, status, currency, amount, stored, list(flags), has_payment, wordpress_id)


class ClassifyTest(SimpleTestCase):
    """The Phase 3 correction matrix, applied to single rows."""

    def test_correctable_rules(self):
        self.assertEqual(classify(RAW_IRR, 'wc-completed', 'IRR', '1965000', 1965000), ('R1A', 'R1A_IRR_DIV10', '0.1', 196500))
        self.assertEqual(classify(RAW_IRR, 'wc-on-hold', 'IRR', '250000000', 250000000, [FLAG_WHOLESALE_SIZED]),
                         ('R1B', 'R1B_IRR_DIV10_WHOLESALE', '0.1', 25000000))
        self.assertEqual(classify(RAW_IRHT, 'wc-completed', 'IRHT', '1425', 1425), ('R2', 'R2_IRHT_X1000', '1000', 1425000))
        self.assertEqual(classify(RAW_IRR, 'wc-cancelled', 'IRR', '74020', 74020), ('R4', 'R4_CANCELLED_CONVERT', '0.1', 7402))
        self.assertEqual(classify(RAW_IRR, 'wc-refunded', 'IRR', '500000', 500000), ('R5', 'R5_REFUND_RELATED_CONVERT', '0.1', 50000))
        self.assertEqual(classify(RAW_IRR, 'wc-completed', 'IRR', '300000', 300000, [FLAG_HAS_REFUND_RECORD])[0], 'R5')

    def test_precedence_excludes_anomalies_zero_uncertain_and_paid_orders(self):
        anomaly = [FLAG_CANCELLED_SEP_ANOMALY, FLAG_WHOLESALE_SIZED]
        self.assertEqual(classify(RAW_IRHT, 'wc-cancelled', 'IRHT', '4400125', 4400125, anomaly), ('R7', 'EXCL_R7_ANOMALY', '', ''))
        self.assertEqual(classify(MATCH, 'wc-completed', 'IRR', '0', 0, [FLAG_ZERO_TOTAL]), ('R3', 'EXCL_R3_ZERO', '', ''))
        self.assertEqual(classify(RAW_IRR, 'wc-completed', 'IRR', '1965000', 1965000, has_payment=True),
                         ('R6', 'EXCL_R6_HAS_PAYMENT', '', ''))
        for audit in (MISMATCH, MISSING_IN_EXPORT, DUPLICATE_IN_EXPORT, SOURCE_INVALID):
            with self.subTest(audit=audit):
                self.assertEqual(classify(audit, 'wc-completed', 'IRR', '1000', 1000), ('R8', f'EXCL_R8_{audit}', '', ''))

    def test_stored_value_equal_to_provisional_conversion_is_review_not_approval(self):
        rule, reason, factor, after = classify(MATCH, 'wc-completed', 'IRR', '1965000', 196500)
        self.assertEqual((rule, reason, factor, after), ('R8', 'REVIEW_STORED_EQUALS_PROVISIONAL_CONVERSION', '', ''))
        self.assertEqual(correction.base_category(reason), correction.OWNER_REVIEW)

    def test_unsupported_or_missing_currency_is_never_converted(self):
        for currency in ('', 'USD', 'irr ', None):
            with self.subTest(currency=currency):
                self.assertEqual(classify(RAW_IRR, 'wc-completed', currency, '1000', 1000)[:2], ('R8', 'EXCL_R8_SOURCE_INVALID'))
        self.assertEqual(classify(RAW_IRR, 'wc-completed', 'IRR', None, 1000)[:2], ('R8', 'EXCL_R8_SOURCE_INVALID'))

    def test_unmapped_status_and_inconsistent_raw_rows_are_not_guessed(self):
        for status in ('wc-processing', 'wc-pending', 'wc-failed', ''):
            with self.subTest(status=status):
                self.assertEqual(classify(RAW_IRR, status, 'IRR', '1000', 1000)[:2], ('R8', 'EXCL_R8_UNMAPPED_STATUS'))
        self.assertEqual(classify(RAW_IRR, 'wc-completed', 'IRR', '1000', 999)[:2], ('R8', 'EXCL_R8_STORED_NOT_RAW'))
        self.assertEqual(classify(RAW_IRR, 'wc-completed', 'IRR', '1000.5', 1000)[:2], ('R8', 'EXCL_R8_SOURCE_NOT_INTEGER'))

    def test_rounding_is_never_applied(self):
        cases = {
            '74025': ('REVIEW_ROUNDING_REQUIRED', ''),
            '15': ('REVIEW_ROUNDING_REQUIRED', ''),
            '5': ('REVIEW_ROUNDING_REQUIRED', ''),
            '1': ('REVIEW_ROUNDING_REQUIRED', ''),
            '10': ('R1A_IRR_DIV10', 1),
            '9007199254740993': ('REVIEW_ROUNDING_REQUIRED', ''),
            '9007199254740990': ('R1A_IRR_DIV10', 900719925474099),
            '99999999999999999999999999999990': ('REJECT_OUT_OF_RANGE', ''),
        }
        for raw, (reason, after) in cases.items():
            with self.subTest(raw=raw):
                _, got_reason, factor, got_after = classify(RAW_IRR, 'wc-completed', 'IRR', raw, int(raw))
                self.assertEqual((got_reason, got_after), (reason, after))
                self.assertEqual(factor, '0.1')
        self.assertEqual(classify(RAW_IRHT, 'wc-completed', 'IRHT', '9223372036854776', 9223372036854776)[1], 'REVIEW_LARGE_IRHT')
        self.assertEqual(correction.base_category('REVIEW_ROUNDING_REQUIRED'), correction.OWNER_REVIEW)
        self.assertEqual(correction.base_category('REJECT_OUT_OF_RANGE'), correction.REJECTED)


class CorrectionFixtureMixin:
    """
    Fictitious orders whose amounts mirror the buckets found in the Phase 3 plan. The command owns
    its transactions, so tests using this mixin are TransactionTestCases. Wordpress id 107 stands in
    for an owner-approved anomaly; the registry and the approval allowlist are patched per test.
    """

    ANOMALY_IDS = frozenset({107})
    SCENARIO = [
        # (wordpress_id, source total, currency, status, method, stored total)
        (101, '1965000', 'IRR', 'wc-completed', 'sep_gateway', 1965000),
        (102, '250000000', 'IRR', 'wc-completed', 'bacs', 250000000),
        (103, '1425', 'IRHT', 'wc-on-hold', 'bacs', 1425),
        (104, '74025', 'IRR', 'wc-cancelled', 'bacs', 74025),
        (105, '500000', 'IRR', 'wc-refunded', 'bacs', 500000),
        (106, '0', 'IRR', 'wc-completed', 'bacs', 0),
        (107, '4400125', 'IRHT', 'wc-cancelled', 'WC_Sep_Payment_Gateway', 4400125),
        (108, 'abc', 'IRR', 'wc-completed', 'bacs', 0),
        (109, '1000', 'USD', 'wc-completed', 'bacs', 1000),
        (110, '1000000', 'IRR', 'wc-completed', 'bacs', 100000),
        (111, '300000', 'IRR', 'wc-completed', 'bacs', 300000),
        (114, '1000', '', 'wc-completed', 'bacs', 1000),
        (115, '2000000', 'IRR', 'wc-on-hold', 'bacs', 2000000),
    ]
    EXPECTED = {
        101: ('PROPOSED', 'R1A', 'R1A_IRR_DIV10', 196500),
        102: ('PROPOSED', 'R1B', 'R1B_IRR_DIV10_WHOLESALE', 25000000),
        103: ('PROPOSED', 'R2', 'R2_IRHT_X1000', 1425000),
        104: ('OWNER_REVIEW', 'R4', 'REVIEW_ROUNDING_REQUIRED', ''),
        105: ('PROPOSED', 'R5', 'R5_REFUND_RELATED_CONVERT', 50000),
        106: ('NO_CHANGE', 'R3', 'EXCL_R3_ZERO', ''),
        107: ('OWNER_REVIEW', 'R7', 'EXCL_R7_APPROVED_ANOMALY_ID', ''),
        108: ('REJECTED', 'R8', 'EXCL_R8_SOURCE_INVALID', ''),
        109: ('REJECTED', 'R8', 'EXCL_R8_SOURCE_INVALID', ''),
        110: ('OWNER_REVIEW', 'R8', 'REVIEW_STORED_EQUALS_PROVISIONAL_CONVERSION', ''),
        111: ('PROPOSED', 'R5', 'R5_REFUND_RELATED_CONVERT', 30000),
        112: ('REJECTED', 'R8', 'EXCL_R8_DUPLICATE_IN_EXPORT', ''),
        113: ('REJECTED', 'R8', 'EXCL_R8_MISSING_IN_EXPORT', ''),
        114: ('REJECTED', 'R8', 'EXCL_R8_SOURCE_INVALID', ''),
        115: ('PROPOSED', 'R1A', 'R1A_IRR_DIV10', 200000),
    }

    def setUp(self):
        super().setUp()
        for name, value in (
            ('APPROVED_ANOMALY_WORDPRESS_IDS', self.ANOMALY_IDS),
            ('EXPECTED_ANOMALY_COUNT', len(self.ANOMALY_IDS)),
            ('AUTHORIZED_APPROVALS', {}),
        ):
            patcher = mock.patch.object(correction, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.orders = {}
        for wp, _, _, status, _, stored in self.SCENARIO:
            self.orders[wp] = OrderFactory(wordpress_id=wp, total_price=stored, is_paid=status in ('wc-completed', 'wc-refunded'),
                                           status=Order.Status.PENDING_PAYMENT, first_name=PII[0], phone_number=PII[2][:15])
        self.orders[112] = OrderFactory(wordpress_id=112, total_price=5000, is_paid=True)
        self.orders[113] = OrderFactory(wordpress_id=113, total_price=777, is_paid=True)
        self.native = OrderFactory(wordpress_id=None, total_price=50000, is_paid=False)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.export = self.dir / 'export.xml'
        self._write_export()
        self.before_state = self.dir / 'before.csv'

    def _export_items(self):
        items = [_order_xml(wp, total, currency, status, method) for wp, total, currency, status, method, _ in self.SCENARIO]
        items += [_order_xml(112, '5000', 'IRR'), _order_xml(112, '6000', 'IRR'), _order_xml('abc', '1000', 'IRR')]
        items += [_refund_xml(9001, 111, '100000')]
        return items

    def _write_export(self, *extra):
        self.export.write_text(_wxr(*self._export_items(), *extra), encoding='utf-8')

    # -- helpers

    def _call(self, *args):
        out = io.StringIO()
        call_command(COMMAND, *[str(a) for a in args], stdout=out, stderr=io.StringIO())
        return out.getvalue()

    def _snapshot(self, *extra, before_state=None):
        if before_state is not None:
            self.before_state = before_state
        out = self._call('--snapshot', '--export', self.export, '--before-state', self.before_state, *extra)
        self.before_sha = self._value(out, 'before_state_sha256')
        return out

    def _preview(self, name, *rules, sha=None):
        args = ['--before-state', self.before_state, '--before-state-sha256', sha or self.before_sha,
                '--preview', self.dir / name]
        for rule in rules:
            args += ['--rule', rule]
        return self._call(*args)

    def _manifest(self):
        return json.loads(Path(f'{self.before_state}.manifest.json').read_text(encoding='utf-8'))

    @staticmethod
    def _value(out, key):
        return next(line.split('=', 1)[1] for line in out.splitlines() if line.startswith(f'{key}='))

    def _rows(self, name):
        with open(self.dir / name, encoding='utf-8', newline='') as handle:
            return list(csv.DictReader(handle))

    def _by_wp(self, name):
        return {int(r['wordpress_id']): r for r in self._rows(name)}

    def _db_state(self):
        return (
            list(Order.objects.order_by('pk').values_list(
                'pk', 'wordpress_id', 'total_price', 'is_paid', 'status', 'user_id', 'datetime_modified')),
            Payment.objects.count(),
        )

    def _approval(self, preview_sha, rule='R1A', factors=None, authorize=True, **overrides):
        """A test approval; authorize records its hash the way a reviewed code change would."""
        manifest = self._manifest()
        data = {
            'format': correction.APPROVAL_FORMAT,
            'approval_ref': 'TEST-ONLY-NOT-A-REAL-APPROVAL',
            'before_state_sha256': self.before_sha,
            'preview_sha256': preview_sha,
            'rules': [rule],
            'currency_factors': factors if factors is not None else {
                'IRR': {'toman_per_unit': '0.1', 'evidence_ref': 'test fixture'},
            },
            'classification_policy_sha256': manifest['classification_policy_sha256'],
            'wholesale_threshold_toman': manifest['wholesale_threshold_toman'],
            'anomaly_wordpress_ids': manifest['classification_policy']['anomaly_wordpress_ids'],
            'database_identity': manifest['database_identity'],
            'imported_orders_fingerprint_sha256': manifest['imported_orders_fingerprint']['sha256'],
        }
        data.update(overrides)
        path = self.dir / f'approval-{len(list(self.dir.iterdir()))}.json'
        body = json.dumps(data).encode('utf-8')
        path.write_bytes(body)
        sha = hashlib.sha256(body).hexdigest()
        if authorize:
            correction.AUTHORIZED_APPROVALS[sha] = data.get('approval_ref')
        return path, sha

    def _apply(self, approval, approval_sha, report='execution.csv', rule='R1A', enabled=True):
        with mock.patch.object(correction, 'EXECUTION_ENABLED', enabled):
            return self._call(
                '--apply', '--rule', rule, '--before-state', self.before_state, '--before-state-sha256', self.before_sha,
                '--approval-file', approval, '--approval-sha256', approval_sha, '--execution-report', self.dir / report,
            )

    def _rollback(self, approval, approval_sha, execution='execution.csv', execution_sha=None, report='rollback.csv',
                  rule='R1A', enabled=True):
        execution_path = self.dir / execution
        execution_sha = execution_sha or hashlib.sha256(execution_path.read_bytes()).hexdigest()
        with mock.patch.object(correction, 'EXECUTION_ENABLED', enabled):
            return self._call(
                '--rollback', '--rule', rule, '--before-state', self.before_state, '--before-state-sha256', self.before_sha,
                '--approval-file', approval, '--approval-sha256', approval_sha, '--execution-report', execution_path,
                '--execution-report-sha256', execution_sha, '--rollback-report', self.dir / report,
            )

    def _ready_to_apply(self, rule='R1A', factors=None):
        self._snapshot()
        preview_sha = self._value(self._preview(f'preview-{rule}.csv', rule), 'preview_sha256')
        return self._approval(preview_sha, rule=rule, factors=factors)

    def _rewrite_before_state(self, transform):
        """Edit the before-state and re-seal the manifest, as a careless or malicious edit would."""
        lines = self.before_state.read_text(encoding='utf-8').splitlines(keepends=True)
        body = ''.join(transform(lines)).encode('utf-8')
        self.before_state.write_bytes(body)
        sha = hashlib.sha256(body).hexdigest()
        manifest_path = Path(f'{self.before_state}.manifest.json')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['before_state_sha256'] = sha
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        return sha


class CorrectionCommandTest(CorrectionFixtureMixin, TransactionTestCase):
    """Snapshot, dry-run preview and the (code-disabled) apply path."""

    # -- snapshot

    def test_snapshot_records_original_values_rules_and_manifest(self):
        out = self._snapshot()
        rows = {int(r['wordpress_id']): r for r in csv.DictReader(io.StringIO(self.before_state.read_text(encoding='utf-8')))}
        manifest = json.loads(Path(f'{self.before_state}.manifest.json').read_text(encoding='utf-8'))

        self.assertEqual(sorted(rows), sorted(self.EXPECTED))
        for wp, (_, rule, reason, after) in self.EXPECTED.items():
            with self.subTest(wp=wp):
                row = rows[wp]
                self.assertEqual((row['rule'], row['reason_code'], row['proposed_after']), (rule, reason, str(after)))
                self.assertEqual(row['order_id'], str(self.orders[wp].pk))
                self.assertEqual(row['total_price_before'], str(self.orders[wp].total_price))
                self.assertEqual(row['is_paid_before'], str(self.orders[wp].is_paid))
        self.assertEqual(manifest['before_state_sha256'], hashlib.sha256(self.before_state.read_bytes()).hexdigest())
        self.assertEqual(manifest['before_state_sha256'], self.before_sha)
        self.assertEqual(manifest['export_sha256'], hashlib.sha256(self.export.read_bytes()).hexdigest())
        self.assertEqual(manifest['rows'], 15)
        self.assertEqual(manifest['rules']['R1A'], {'orders': '2', 'proposed': '2', 'total_price_before': '3965000', 'proposed_after': '396500'})
        self.assertEqual(manifest['imported_orders_fingerprint']['count'], 15)
        self.assertEqual({v['status'] for v in manifest['conversion_factors'].values()}, {'PROVISIONAL_UNAPPROVED'})
        self.assertIn('not evidence of approval', manifest['notice'])
        self.assertIn('not evidence of approval', out)
        self.assertEqual(manifest['format'], 'kasra-order-amount-before-state/v2')
        self.assertEqual(manifest['classification_policy'], correction.classification_policy())
        self.assertEqual(manifest['classification_policy_sha256'], correction.policy_sha256(correction.classification_policy()))
        self.assertEqual(manifest['classification_policy']['anomaly_wordpress_ids'], [107])
        self.assertEqual((manifest['wholesale_threshold_toman'], manifest['wholesale_threshold_reviewed']), ('20000000', True))
        self.assertEqual(manifest['database_identity']['vendor'], connection.vendor)

    def test_snapshot_and_preview_make_no_database_changes(self):
        before = self._db_state()
        with CaptureQueriesContext(connection) as ctx:
            self._snapshot()
            self._preview('preview.csv')
        writes = [q['sql'] for q in ctx.captured_queries if q['sql'].lstrip().upper().startswith(WRITE_SQL)]
        self.assertEqual(writes, [])
        self.assertEqual(self._db_state(), before)

    def test_artifacts_contain_no_personal_data(self):
        out = self._snapshot() + self._preview('preview.csv')
        texts = [out] + [p.read_text(encoding='utf-8') for p in self.dir.iterdir() if p.suffix in ('.csv', '.json')]
        for text in texts:
            for secret in PII:
                self.assertNotIn(secret, text)

    # -- preview

    def test_preview_separates_categories_and_is_marked_unapproved(self):
        self._snapshot()
        out = self._preview('preview.csv')
        rows = self._by_wp('preview.csv')

        for wp, (category, rule, reason, after) in self.EXPECTED.items():
            with self.subTest(wp=wp):
                self.assertEqual((rows[wp]['category'], rows[wp]['rule'], rows[wp]['reason_code'], rows[wp]['proposed_after']),
                                 (category, rule, reason, str(after)))
        self.assertNotIn(self.native.pk, [int(r['order_id']) for r in rows.values()])
        self.assertEqual({r['factor_status'] for r in rows.values() if r['factor']}, {'PROVISIONAL_UNAPPROVED'})
        self.assertFalse(any(cell == 'APPROVED' for r in rows.values() for cell in r.values()))
        self.assertIn('DRY RUN: no data was changed', out)
        self.assertIn('Nothing in this output is approved.', out)
        self.assertIn('category PROPOSED: 6', out)
        self.assertIn('proposed R1A: orders=2 before_sum=3965000 after_sum=396500', out)
        self.assertIn('fingerprint=MATCHES_BEFORE_STATE', out)
        self.assertEqual(rows[101]['delta'], str(196500 - 1965000))

    def test_preview_is_deterministic(self):
        self._snapshot()
        first = self._preview('a.csv', 'R1A')
        second = self._preview('b.csv', 'R1A')

        self.assertEqual((self.dir / 'a.csv').read_bytes(), (self.dir / 'b.csv').read_bytes())
        self.assertEqual(self._value(first, 'preview_sha256'), self._value(second, 'preview_sha256'))
        self.assertEqual(first.replace('a.csv', 'b.csv'), second)
        summary_a = json.loads((self.dir / 'a.csv.summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary_a['preview_sha256'], hashlib.sha256((self.dir / 'a.csv').read_bytes()).hexdigest())

    def test_rule_selection_marks_other_batches_not_selected(self):
        self._snapshot()
        self._preview('preview.csv', 'R1A')
        rows = self._by_wp('preview.csv')
        self.assertEqual({wp for wp, r in rows.items() if r['category'] == 'PROPOSED'}, {101, 115})
        self.assertEqual({wp for wp, r in rows.items() if r['category'] == 'NOT_SELECTED'}, {102, 103, 105, 111})

    def test_preview_detects_database_changes_after_the_snapshot(self):
        self._snapshot()
        Order.objects.filter(wordpress_id=101).update(total_price=1)
        Order.objects.filter(wordpress_id=103).update(is_paid=True)
        Payment.objects.create(order=self.orders[102], gateway='sep', amount=1, status=Payment.Status.FAILED)
        self.orders[105].delete()
        late = OrderFactory(wordpress_id=999, total_price=10)

        self._preview('preview.csv')
        rows = self._by_wp('preview.csv')

        self.assertEqual(rows[101]['reason_code'], 'DB_TOTAL_CHANGED')
        self.assertEqual(rows[101]['total_price_current'], '1')
        self.assertEqual(rows[103]['reason_code'], 'DB_IS_PAID_CHANGED')
        self.assertEqual(rows[102]['reason_code'], 'DB_PAYMENT_ADDED')
        self.assertEqual(rows[105]['reason_code'], 'DB_ORDER_MISSING')
        self.assertEqual((rows[999]['reason_code'], rows[999]['order_id']), ('NOT_IN_BEFORE_STATE', str(late.pk)))
        for wp in (101, 102, 103, 105, 999):
            self.assertEqual(rows[wp]['category'], 'CONFLICT')

    # -- before-state validation

    def _assert_preview_rejected(self, message, sha=None):
        with self.assertRaisesMessage(CommandError, message):
            self._preview('rejected.csv', sha=sha)
        self.assertFalse((self.dir / 'rejected.csv').exists())
        self.assertFalse((self.dir / 'rejected.csv.summary.json').exists())

    def test_missing_before_state_or_manifest_is_rejected(self):
        self.before_sha = '0' * 64
        self._assert_preview_rejected('Before-state file not found')
        self._snapshot()
        Path(f'{self.before_state}.manifest.json').unlink()
        self._assert_preview_rejected('Before-state manifest not found')

    def test_before_state_hash_is_required_and_checked(self):
        self._snapshot()
        self._assert_preview_rejected('does not match --before-state-sha256', sha='f' * 64)
        self._assert_preview_rejected('64-character hexadecimal', sha='not-a-hash')
        with self.assertRaisesMessage(CommandError, '64-character hexadecimal'):
            self._call('--before-state', self.before_state, '--preview', self.dir / 'x.csv')

    def test_edited_before_state_is_rejected_even_when_resealed(self):
        cases = {
            'proposed value': (lambda ls: [ls[0]] + [l.replace(',196500\n', ',196501\n') for l in ls[1:]], 'does not match the correction rules'),
            'consistent edit of before, source and proposed': (
                lambda ls: [ls[0]] + [l.replace(',196500', ',196501') for l in ls[1:]], 'per-rule counts or sums'),
            'stored total': (lambda ls: [ls[0]] + [l.replace(',1965000,', ',1965001,', 1) for l in ls[1:]], 'does not match the correction rules'),
            'duplicate row': (lambda ls: ls + [ls[1]], 'duplicate order_id or wordpress_id'),
            'malformed id': (lambda ls: [ls[0], 'abc' + ls[1][ls[1].index(','):]] + ls[2:], 'order_id is not a non-negative integer'),
            'zero id': (lambda ls: [ls[0], '0' + ls[1][ls[1].index(','):]] + ls[2:], 'order_id is out of range'),
            'negative total': (lambda ls: [ls[0]] + [l.replace(',1965000,', ',-1965000,', 1) for l in ls[1:]], 'total_price_before is not a non-negative integer'),
            'header': (lambda ls: ['order_id,wp\n'] + ls[1:], 'header does not match'),
            'short row': (lambda ls: ls[:1] + ['1,2,3\n'] + ls[2:], 'expected 14 columns'),
            'missing row': (lambda ls: ls[:-1], 'row count does not match the manifest'),
            'unsupported currency': (lambda ls: [ls[0]] + [l.replace(',IRHT,', ',USD,') for l in ls[1:]], 'unsupported source_currency'),
            'unknown flag': (lambda ls: [ls[0]] + [l.replace('ZERO_TOTAL', 'APPROVED') for l in ls[1:]], 'unknown flag'),
        }
        for name, (transform, message) in cases.items():
            with self.subTest(case=name):
                self._snapshot_fresh()
                sha = self._rewrite_before_state(transform)
                self._assert_preview_rejected(message, sha=sha)

    def _snapshot_fresh(self):
        for path in (self.before_state, Path(f'{self.before_state}.manifest.json')):
            path.unlink(missing_ok=True)
        self._snapshot()

    def test_manifest_problems_are_rejected(self):
        manifest_path = Path(f'{self.before_state}.manifest.json')
        cases = {
            'invalid json': (lambda m: '{not json', 'not valid JSON'),
            'unknown format': (lambda m: json.dumps({**m, 'format': 'other'}), 'unknown format'),
            'factor changed': (lambda m: json.dumps({**m, 'conversion_factors': {
                **m['conversion_factors'], 'IRHT': {'toman_per_unit': '100', 'status': 'PROVISIONAL_UNAPPROVED'}}}),
                'Conversion factors changed'),
            'rule sums': (lambda m: json.dumps({**m, 'rules': {**m['rules'], 'R1A': {**m['rules']['R1A'], 'proposed_after': '1'}}}),
                          'per-rule counts or sums'),
            'other file': (lambda m: json.dumps({**m, 'before_state_sha256': 'a' * 64}), 'records a different SHA-256'),
        }
        for name, (transform, message) in cases.items():
            with self.subTest(case=name):
                self._snapshot_fresh()
                manifest_path.write_text(transform(json.loads(manifest_path.read_text(encoding='utf-8'))), encoding='utf-8')
                self._assert_preview_rejected(message)

    def test_factor_change_in_code_invalidates_the_before_state(self):
        self._snapshot()
        with mock.patch.dict(correction.TOMAN_PER_UNIT, {'IRHT': Decimal('100')}):
            self._assert_preview_rejected('Conversion factors changed')

    # -- report destinations

    def test_existing_or_unwritable_destinations_are_refused_before_any_work(self):
        self._snapshot()
        (self.dir / 'taken.csv').write_text('keep', encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'already exists'):
            self._preview('taken.csv')
        self.assertEqual((self.dir / 'taken.csv').read_text(encoding='utf-8'), 'keep')
        with self.assertRaisesMessage(CommandError, 'Output directory does not exist'):
            self._preview('missing/preview.csv')
        with self.assertRaisesMessage(CommandError, 'already exists'):
            self._snapshot()
        with self.assertRaisesMessage(CommandError, 'Output directory does not exist'):
            self._call('--snapshot', '--export', self.export, '--before-state', self.dir / 'missing' / 'b.csv')

    def test_failed_write_leaves_no_partial_report(self):
        self._snapshot()
        real_write = correction.Outputs.write
        calls = []

        def write_then_fail(outputs, path, data):
            calls.append(path)
            if len(calls) == 2:
                raise OSError(28, 'No space left on device')
            return real_write(outputs, path, data)

        with mock.patch.object(correction.Outputs, 'write', write_then_fail):
            with self.assertRaises(OSError):
                self._preview('preview.csv')
        self.assertFalse((self.dir / 'preview.csv').exists())
        self.assertFalse((self.dir / 'preview.csv.summary.json').exists())

    def test_snapshot_without_export_or_with_bad_export_writes_nothing(self):
        with self.assertRaisesMessage(CommandError, 'requires --export'):
            self._call('--snapshot', '--before-state', self.before_state)
        self.export.write_text('<rss><channel>', encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'not valid XML'):
            self._snapshot()
        self.assertFalse(self.before_state.exists())
        self.assertFalse(Path(f'{self.before_state}.manifest.json').exists())

    # -- apply guards

    def test_apply_is_disabled_in_code_even_with_valid_inputs(self):
        approval, approval_sha = self._ready_to_apply()
        before = self._db_state()
        with self.assertRaisesMessage(CommandError, 'Execution is disabled in this build'):
            self._apply(approval, approval_sha, enabled=False)
        self.assertEqual(self._db_state(), before)
        self.assertFalse((self.dir / 'execution.csv').exists())
        self.assertFalse(correction.EXECUTION_ENABLED)

    def test_apply_refuses_unapproved_or_mismatched_approvals(self):
        approval, approval_sha = self._ready_to_apply()
        preview_sha = json.loads(approval.read_text(encoding='utf-8'))['preview_sha256']
        before = self._db_state()
        cases = [
            (self._approval(preview_sha, factors={}), 'Conversion factor for IRR is not approved'),
            (self._approval(preview_sha, factors={'IRR': {'toman_per_unit': '0.01', 'evidence_ref': 'x'}}),
             'differs from the factor in code'),
            (self._approval(preview_sha, factors={'IRR': {'toman_per_unit': 0.1, 'evidence_ref': 'x'}}),
             'must be a decimal string'),
            (self._approval(preview_sha, factors={'IRR': {'toman_per_unit': '0.1', 'evidence_ref': ' '}}),
             'non-empty evidence_ref'),
            (self._approval(preview_sha, rules=['R1A', 'R2']), 'does not approve exactly the selected rule'),
            (self._approval(preview_sha, before_state_sha256='b' * 64), 'bound to a different before-state'),
            (self._approval('c' * 64), 'does not match the approved preview_sha256'),
            (self._approval(preview_sha, approval_ref=''), 'has no approval_ref'),
            (self._approval(preview_sha, approved='yes'), 'must contain exactly these keys'),
            ((approval, 'd' * 64), 'does not match --approval-sha256'),
            (self._approval(preview_sha, authorize=False, approval_ref='UNRECORDED'), 'not recorded in AUTHORIZED_APPROVALS'),
            (self._approval(preview_sha, classification_policy_sha256='e' * 64), 'different classification policy'),
            (self._approval(preview_sha, wholesale_threshold_toman='999999999'), 'different wholesale threshold'),
            (self._approval(preview_sha, anomaly_wordpress_ids=[]), 'different anomaly ids'),
            (self._approval(preview_sha, database_identity={'vendor': 'postgresql'}), 'bound to a different database'),
            (self._approval(preview_sha, imported_orders_fingerprint_sha256='f' * 64), 'different set of imported orders'),
        ]
        relabelled, relabelled_sha = self._approval(preview_sha, approval_ref='RELABELLED')
        correction.AUTHORIZED_APPROVALS[relabelled_sha] = 'ANOTHER-RECORD'
        cases.append(((relabelled, relabelled_sha), 'differs from the reference recorded'))
        for index, ((path, sha), message) in enumerate(cases):
            with self.subTest(message=message):
                with self.assertRaisesMessage(CommandError, message):
                    self._apply(path, sha, report=f'exec-{index}.csv')
                self.assertFalse((self.dir / f'exec-{index}.csv').exists())
        self.assertEqual(self._db_state(), before)

    def test_apply_for_irht_requires_an_irht_factor_approval(self):
        approval, approval_sha = self._ready_to_apply(rule='R2')
        with self.assertRaisesMessage(CommandError, 'Conversion factor for IRHT is not approved'):
            self._apply(approval, approval_sha, rule='R2')
        self.assertEqual(Order.objects.get(wordpress_id=103).total_price, 1425)

    def test_apply_refuses_when_the_database_changed_after_the_snapshot(self):
        approval, approval_sha = self._ready_to_apply()
        Order.objects.filter(wordpress_id=115).update(total_price=2000001)
        with self.assertRaisesMessage(CommandError, 'changed since the before-state'):
            self._apply(approval, approval_sha)
        self.assertEqual(Order.objects.get(wordpress_id=101).total_price, 1965000)
        self.assertFalse((self.dir / 'execution.csv').exists())

    def test_apply_refuses_when_a_payment_appears_for_a_target(self):
        approval, approval_sha = self._ready_to_apply()
        Payment.objects.create(order=self.orders[101], gateway='sep', amount=1, status=Payment.Status.FAILED)
        with self.assertRaisesMessage(CommandError, 'changed since the before-state'):
            self._apply(approval, approval_sha)
        self.assertEqual(Order.objects.get(wordpress_id=101).total_price, 1965000)

    def test_apply_argument_guards(self):
        approval, approval_sha = self._ready_to_apply()
        with mock.patch.object(correction, 'EXECUTION_ENABLED', True):
            with self.assertRaisesMessage(CommandError, 'exactly one --rule'):
                self._call('--apply', '--before-state', self.before_state)
            with self.assertRaisesMessage(CommandError, '--apply requires --approval-file'):
                self._call('--apply', '--rule', 'R1A', '--before-state', self.before_state)
        with self.assertRaisesMessage(CommandError, 'only valid with --apply'):
            self._call('--before-state', self.before_state, '--before-state-sha256', self.before_sha,
                       '--preview', self.dir / 'p.csv', '--approval-file', approval)
        with self.assertRaises(CommandError):
            self._call('--apply', '--rule', 'R3', '--before-state', self.before_state)

    # -- apply with execution enabled in the test only

    def test_apply_updates_only_the_approved_batch_with_compare_and_set(self):
        approval, approval_sha = self._ready_to_apply()
        before = {o.wordpress_id: (o.total_price, o.is_paid, o.status, o.datetime_modified) for o in Order.objects.all()}

        out = self._apply(approval, approval_sha)

        after = {o.wordpress_id: (o.total_price, o.is_paid, o.status, o.datetime_modified) for o in Order.objects.all()}
        self.assertIn('R1A: 2 corrections committed', out)
        self.assertEqual(after[101], (196500,) + before[101][1:])
        self.assertEqual(after[115], (200000,) + before[115][1:])
        self.assertEqual({k: v for k, v in after.items() if k not in (101, 115)},
                         {k: v for k, v in before.items() if k not in (101, 115)})
        rows = self._rows('execution.csv')
        self.assertEqual([(r['status'], r['wordpress_id'], r['total_price_before'], r['total_price_after']) for r in rows],
                         [('INTENDED', '101', '1965000', '196500'), ('INTENDED', '115', '2000000', '200000'),
                          ('RUN_STARTED', '', '3965000', '396500'), ('RUN_COMMITTED', '', '3965000', '396500')])
        self.assertEqual({r['approval_sha256'] for r in rows}, {approval_sha})
        self.assertEqual({r['before_state_sha256'] for r in rows}, {self.before_sha})

        self._preview('after.csv', 'R1A')
        preview = self._by_wp('after.csv')
        self.assertEqual({preview[101]['category'], preview[115]['category']}, {'ALREADY_APPLIED'})

    def test_repeated_apply_is_a_no_op(self):
        approval, approval_sha = self._ready_to_apply()
        self._apply(approval, approval_sha)
        state = self._db_state()

        with CaptureQueriesContext(connection) as ctx:
            out = self._apply(approval, approval_sha, report='second.csv')

        writes = [q['sql'] for q in ctx.captured_queries if q['sql'].lstrip().upper().startswith(WRITE_SQL)]
        self.assertEqual(writes, [])
        self.assertEqual(self._db_state(), state)
        self.assertIn('Nothing to apply: all 2 R1A corrections are already applied', out)
        self.assertEqual(self._rows('second.csv')[-1]['status'], 'RUN_NOOP_ALREADY_APPLIED')

    def test_partially_applied_batch_is_refused(self):
        approval, approval_sha = self._ready_to_apply()
        self._apply(approval, approval_sha)
        Order.objects.filter(wordpress_id=115).update(total_price=2000000)
        with self.assertRaisesMessage(CommandError, 'refusing a mixed state'):
            self._apply(approval, approval_sha, report='again.csv')
        self.assertEqual(Order.objects.get(wordpress_id=101).total_price, 196500)
        self.assertEqual(Order.objects.get(wordpress_id=115).total_price, 2000000)

    def test_failure_mid_batch_rolls_back_everything_and_a_retry_succeeds(self):
        approval, approval_sha = self._ready_to_apply()
        real = correction.Command._compare_and_set
        calls = []

        def fail_second(using, target):
            calls.append(target['wordpress_id'])
            if len(calls) == 2:
                raise RuntimeError('simulated database failure')
            return real(using, target)

        with mock.patch.object(correction.Command, '_compare_and_set', staticmethod(fail_second)):
            with self.assertRaisesMessage(CommandError, 'rolled back (RuntimeError)'):
                self._apply(approval, approval_sha)

        self.assertEqual(Order.objects.get(wordpress_id=101).total_price, 1965000)
        self.assertEqual(Order.objects.get(wordpress_id=115).total_price, 2000000)
        self.assertEqual([r['status'] for r in self._rows('execution.csv')],
                         ['INTENDED', 'INTENDED', 'RUN_STARTED', 'RUN_ROLLED_BACK'])

        self._apply(approval, approval_sha, report='retry.csv')
        self.assertEqual(Order.objects.get(wordpress_id=101).total_price, 196500)
        self.assertEqual(Order.objects.get(wordpress_id=115).total_price, 200000)

    def test_concurrent_change_during_apply_rolls_back(self):
        approval, approval_sha = self._ready_to_apply()
        real = correction.Command._compare_and_set
        calls = []

        def edit_then_update(using, target):
            calls.append(target['wordpress_id'])
            if len(calls) == 2:
                Order.objects.filter(pk=target['order_id']).update(total_price=target['total_price_before'] + 1)
            return real(using, target)

        with mock.patch.object(correction.Command, '_compare_and_set', staticmethod(edit_then_update)):
            with self.assertRaisesMessage(CommandError, 'changed during the run'):
                self._apply(approval, approval_sha)
        self.assertEqual(Order.objects.get(wordpress_id=101).total_price, 1965000)
        self.assertEqual(Order.objects.get(wordpress_id=115).total_price, 2000000)
        self.assertEqual(self._rows('execution.csv')[-1]['status'], 'RUN_ROLLED_BACK')

    def test_existing_execution_report_is_refused_before_any_write(self):
        approval, approval_sha = self._ready_to_apply()
        (self.dir / 'execution.csv').write_text('keep', encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'already exists'):
            self._apply(approval, approval_sha)
        self.assertEqual(Order.objects.get(wordpress_id=101).total_price, 1965000)
        self.assertEqual((self.dir / 'execution.csv').read_text(encoding='utf-8'), 'keep')

    def test_corrected_imported_orders_stay_unpayable(self):
        approval, approval_sha = self._ready_to_apply()
        self._apply(approval, approval_sha)

        for wp, code in ((101, 'ORDER_ALREADY_PAID'), (115, 'ORDER_NOT_PAYABLE')):
            with self.subTest(wp=wp):
                order = Order.objects.get(wordpress_id=wp)
                self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)
                self.assertTrue(order.is_imported)
                self.assertFalse(order.is_payable())
                self.assertFalse(order.can_transition_to(Order.Status.PAID))
                with self.assertRaises(services.PaymentError) as ctx:
                    services.start_payment(order, 'https://example.test/payment/verify/')
                self.assertEqual(ctx.exception.code, code)
                self.assertFalse(Payment.objects.filter(order=order).exists())
        self.native.refresh_from_db()
        self.assertEqual((self.native.total_price, self.native.wordpress_id), (50000, None))
