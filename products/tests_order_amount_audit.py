import csv
import io
import random
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import skipUnless
from xml.sax.saxutils import escape

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from orders.factories import OrderFactory
from orders.models import Order
from products.management.commands.audit_imported_order_amounts import (
    CSV_COLUMNS,
    SourceOrder,
    SourceRefund,
    read_imported_totals,
    reconcile,
)

PII = ('Secret Name', 'secret.buyer@example.com', '09121112233', 'Secret Street 12')


def _order_xml(wp_id, total, currency='IRR', status='wc-completed', method='bacs'):
    metas = {
        '_order_total': total,
        '_order_currency': currency,
        '_payment_method': method,
        '_billing_first_name': PII[0],
        '_billing_email': PII[1],
        '_billing_phone': PII[2],
        '_billing_address_1': PII[3],
    }
    meta_xml = ''.join(
        f'<wp:postmeta><wp:meta_key>{k}</wp:meta_key><wp:meta_value>{escape(str(v))}</wp:meta_value></wp:postmeta>'
        for k, v in metas.items()
    )
    return (
        f'<item><title>Order {wp_id}</title><wp:post_id>{wp_id}</wp:post_id>'
        f'<wp:post_type>shop_order</wp:post_type><wp:status>{escape(status)}</wp:status>{meta_xml}'
        f'<wp:comment><wp:comment_content>{PII[0]} paid, call {PII[2]}</wp:comment_content></wp:comment></item>'
    )


def _refund_xml(wp_id, parent, amount, currency='IRR'):
    return (
        f'<item><wp:post_id>{wp_id}</wp:post_id><wp:post_parent>{parent}</wp:post_parent>'
        f'<wp:post_type>shop_order_refund</wp:post_type>'
        f'<wp:postmeta><wp:meta_key>_refund_amount</wp:meta_key><wp:meta_value>{amount}</wp:meta_value></wp:postmeta>'
        f'<wp:postmeta><wp:meta_key>_order_currency</wp:meta_key><wp:meta_value>{currency}</wp:meta_value></wp:postmeta>'
        f'</item>'
    )


def _wxr(*items):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:wp="http://wordpress.org/export/1.2/"><channel>'
        + ''.join(items) + '</channel></rss>'
    )


def _by_id(report):
    return {(r['record_type'], str(r['wordpress_id'])): r for r in report.rows}


class ReconcileClassificationTest(SimpleTestCase):
    def test_each_classification(self):
        orders = [
            SourceOrder('1', 'wc-completed', 'IRR', '1965000'),
            SourceOrder('2', 'wc-completed', 'IRR', '1965000'),
            SourceOrder('3', 'wc-completed', 'IRHT', '1425'),
            SourceOrder('4', 'wc-completed', 'IRHT', '1425'),
            SourceOrder('5', 'wc-completed', 'IRR', '1965000'),
            SourceOrder('6', 'wc-completed', 'IRR', '1000'),
        ]
        db = [(1, 196500), (2, 1965000), (3, 1425000), (4, 1425), (5, 123), (99, 5000)]
        rows = _by_id(reconcile(orders, [], db))

        self.assertEqual(rows[('order', '1')]['classification'], 'MATCH')
        self.assertEqual(rows[('order', '2')]['classification'], 'RAW_IRR')
        self.assertEqual(rows[('order', '3')]['classification'], 'MATCH')
        self.assertEqual(rows[('order', '4')]['classification'], 'RAW_IRHT')
        self.assertEqual(rows[('order', '5')]['classification'], 'MISMATCH')
        self.assertEqual(rows[('order', '6')]['classification'], 'MISSING_IN_DB')
        self.assertEqual(rows[('order', '99')]['classification'], 'MISSING_IN_EXPORT')
        self.assertEqual(rows[('order', '2')]['discrepancy'], 1965000 - 196500)
        self.assertEqual(rows[('order', '6')]['stored_total'], '')
        self.assertEqual(rows[('order', '99')]['expected_toman'], '')

    def test_fractional_source_imported_by_truncation_is_raw(self):
        rows = _by_id(reconcile([SourceOrder('1', 'wc-on-hold', 'IRHT', '29028.2')], [], [(1, 29028)]))
        self.assertEqual(rows[('order', '1')]['classification'], 'RAW_IRHT')
        self.assertEqual(rows[('order', '1')]['expected_toman'], 29028200)

    def test_zero_total_policy(self):
        orders = [
            SourceOrder('1', 'wc-completed', 'IRR', '0'),
            SourceOrder('2', 'wc-completed', 'IRHT', '0.00'),
            SourceOrder('3', 'wc-completed', 'IRR', '0'),
        ]
        rows = _by_id(reconcile(orders, [], [(1, 0), (2, 0), (3, 7)]))
        for wp_id in ('1', '2'):
            self.assertEqual(rows[('order', wp_id)]['classification'], 'MATCH')
            self.assertIn('ZERO_TOTAL', rows[('order', wp_id)]['flags'])
        self.assertEqual(rows[('order', '3')]['classification'], 'MISMATCH')

    def test_currency_is_never_guessed(self):
        orders = [
            SourceOrder('1', 'wc-completed', '', '1965000'),
            SourceOrder('2', 'wc-completed', 'USD', '1965000'),
            SourceOrder('3', 'wc-completed', 'IRR', '1,965,000'),
            SourceOrder('4', 'wc-completed', 'IRR', ''),
            SourceOrder('5', 'wc-completed', 'IRR', '-10'),
        ]
        db = [(1, 196500), (2, 196500), (3, 196500), (4, 0), (5, 1)]
        rows = _by_id(reconcile(orders, [], db))
        for wp_id in ('1', '2', '3', '4', '5'):
            self.assertEqual(rows[('order', wp_id)]['classification'], 'SOURCE_INVALID')
            self.assertEqual(rows[('order', wp_id)]['expected_toman'], '')
            self.assertEqual(rows[('order', wp_id)]['discrepancy'], '')
        self.assertIn('INVALID_SOURCE_CURRENCY', rows[('order', '1')]['flags'])
        self.assertIn('INVALID_SOURCE_CURRENCY', rows[('order', '2')]['flags'])
        self.assertIn('INVALID_SOURCE_AMOUNT', rows[('order', '3')]['flags'])

    def test_invalid_source_id(self):
        rows = reconcile([SourceOrder('abc', 'wc-completed', 'IRR', '10')], [], []).rows
        self.assertEqual(rows[0]['classification'], 'SOURCE_INVALID')
        self.assertIn('INVALID_SOURCE_ID', rows[0]['flags'])

    def test_duplicates_are_errors_not_compared(self):
        orders = [
            SourceOrder('5', 'wc-completed', 'IRR', '1000'),
            SourceOrder('5', 'wc-cancelled', 'IRR', '2000'),
            SourceOrder('6', 'wc-completed', 'IRR', '1000'),
        ]
        db = [(5, 100), (6, 100), (6, 1000), (7, 1), (7, 2)]
        report = reconcile(orders, [], db)
        by_class = [(r['wordpress_id'], r['classification']) for r in report.rows]

        self.assertEqual(by_class.count((5, 'DUPLICATE_IN_EXPORT')), 2)
        self.assertIn((6, 'DUPLICATE_IN_DB'), by_class)
        self.assertEqual(by_class.count((7, 'DUPLICATE_IN_DB')), 2)
        self.assertTrue(all(r['discrepancy'] == '' for r in report.rows))
        self.assertEqual(report.summary['source']['duplicate_ids_in_export'], 1)
        self.assertEqual(report.summary['database']['duplicate_ids_in_db'], 2)

    def test_flags(self):
        orders = [
            SourceOrder('1', 'wc-refunded', 'IRR', '1000000'),
            SourceOrder('2', 'wc-completed', 'IRR', '1000000'),
            SourceOrder('3', 'wc-completed', 'IRR', '200000010'),
            SourceOrder('4', 'wc-completed', 'IRR', '200000000'),
            SourceOrder('5', 'wc-cancelled', 'IRHT', '4400125', 'WC_Sep_Payment_Gateway'),
            SourceOrder('6', 'wc-completed', 'IRHT', '40858', 'bacs'),
            SourceOrder('7', 'wc-completed', 'IRR', '1965005'),
        ]
        refunds = [
            SourceRefund('101', '1', 'IRR', '1000000'),
            SourceRefund('102', '2', 'IRR', '500000'),
            SourceRefund('103', '777', 'IRR', '300000'),
            SourceRefund('104', '0', 'IRHT', '750'),
        ]
        report = reconcile(orders, refunds, [])
        rows = _by_id(report)

        self.assertIn('REFUNDED_STATUS', rows[('order', '1')]['flags'])
        self.assertIn('HAS_REFUND_RECORD', rows[('order', '1')]['flags'])
        self.assertNotIn('REFUNDED_STATUS', rows[('order', '2')]['flags'])
        self.assertIn('HAS_REFUND_RECORD', rows[('order', '2')]['flags'])
        self.assertIn('WHOLESALE_SIZED', rows[('order', '3')]['flags'])
        self.assertNotIn('WHOLESALE_SIZED', rows[('order', '4')]['flags'])
        self.assertIn('CANCELLED_SEP_ANOMALY', rows[('order', '5')]['flags'])
        self.assertIn('WHOLESALE_SIZED', rows[('order', '6')]['flags'])
        self.assertNotIn('CANCELLED_SEP_ANOMALY', rows[('order', '6')]['flags'])
        self.assertIn('IRR_NOT_DIVISIBLE_BY_10', rows[('order', '7')]['flags'])
        self.assertNotIn('IRR_NOT_DIVISIBLE_BY_10', rows[('order', '2')]['flags'])

        orphans = {r['wordpress_id']: r for r in report.rows if r['record_type'] == 'refund'}
        self.assertEqual(set(orphans), {'103', '104'})
        self.assertIn('REFUND_WITHOUT_PARENT', orphans['103']['flags'])
        self.assertEqual(orphans['104']['expected_toman'], 750000)
        self.assertEqual(report.summary['source']['refunds_without_parent'], 2)
        self.assertEqual(report.summary['source']['flags']['REFUND_WITHOUT_PARENT'], 2)

    def test_wholesale_threshold_is_configurable(self):
        rows = _by_id(reconcile([SourceOrder('1', 'wc-completed', 'IRR', '1000')], [], [], wholesale_threshold='50'))
        self.assertIn('WHOLESALE_SIZED', rows[('order', '1')]['flags'])

    def test_sep_anomaly_flag_ignores_the_wholesale_threshold(self):
        orders = [
            SourceOrder('1', 'wc-cancelled', 'IRHT', '4400125', 'WC_Sep_Payment_Gateway'),
            SourceOrder('2', 'wc-cancelled', 'IRHT', '20000', 'WC_Sep_Payment_Gateway'),
        ]
        for threshold in ('0', '999999999999999'):
            with self.subTest(threshold=threshold):
                rows = _by_id(reconcile(orders, [], [], wholesale_threshold=threshold))
                self.assertIn('CANCELLED_SEP_ANOMALY', rows[('order', '1')]['flags'])
                self.assertNotIn('CANCELLED_SEP_ANOMALY', rows[('order', '2')]['flags'])

    def test_decimal_aggregates(self):
        orders = [
            SourceOrder('1', 'wc-completed', 'IRR', '1965000'),
            SourceOrder('2', 'wc-completed', 'IRR', '1965005'),
            SourceOrder('3', 'wc-on-hold', 'IRHT', '29028.2'),
            SourceOrder('4', 'wc-cancelled', 'IRHT', '1425'),
        ]
        db = [(1, 1965000), (2, 196501), (3, 29028), (4, 1425000)]
        summary = reconcile(orders, [], db).summary
        irr = summary['source']['orders_by_currency']['IRR']
        irht = summary['source']['orders_by_currency']['IRHT']

        self.assertEqual(irr['source_amount'], Decimal('3930005'))
        self.assertEqual(irr['expected_toman'], Decimal(196500 + 196501))
        self.assertEqual(irr['stored_total'], Decimal(1965000 + 196501))
        self.assertEqual(irr['discrepancy'], Decimal(1965000 - 196500))
        self.assertEqual(irht['source_amount'], Decimal('30453.2'))
        self.assertEqual(irht['expected_toman'], Decimal(29028200 + 1425000))
        self.assertEqual(irht['discrepancy'], Decimal(29028 - 29028200))
        for bucket in (irr, irht):
            for key in ('source_amount', 'expected_toman', 'stored_total', 'discrepancy'):
                self.assertIsInstance(bucket[key], Decimal)

        rec = summary['reconciliation']
        self.assertEqual(rec['by_classification'], {'MATCH': 2, 'RAW_IRHT': 1, 'RAW_IRR': 1})
        self.assertEqual(rec['discrepancy'], rec['stored_total'] - rec['expected_toman'])
        self.assertEqual(summary['source']['orders_by_status'], {'wc-cancelled': 1, 'wc-completed': 2, 'wc-on-hold': 1})

    def test_skip_db_compares_nothing(self):
        report = reconcile([SourceOrder('1', 'wc-completed', 'IRR', '10')], [], None)
        self.assertEqual(report.rows[0]['classification'], 'NOT_COMPARED')
        self.assertFalse(report.summary['database']['inspected'])
        self.assertTrue(any('not inspected' in a for a in report.summary['assumptions']))

    def test_empty_dataset(self):
        report = reconcile([], [], [])
        self.assertEqual(report.rows, [])
        self.assertEqual(report.summary['reconciliation']['by_classification'], {})
        self.assertEqual(report.summary['reconciliation']['discrepancy'], Decimal(0))
        self.assertEqual(report.summary['database']['imported_orders'], 0)

    def test_result_does_not_depend_on_input_order(self):
        orders = [SourceOrder(str(i), 'wc-completed', 'IRR', str(i * 1000)) for i in range(1, 30)]
        db = [(i, i * 100) for i in range(1, 35)]
        first = reconcile(orders, [], db)
        shuffled_orders, shuffled_db = orders[:], db[:]
        random.Random(7).shuffle(shuffled_orders)
        random.Random(7).shuffle(shuffled_db)
        second = reconcile(shuffled_orders, [], shuffled_db)
        self.assertEqual(first.rows, second.rows)
        self.assertEqual(first.summary, second.summary)


class AuditCommandTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.export = self.dir / 'export.xml'
        self.export.write_text(_wxr(
            _order_xml(9001, '1965000'),
            _order_xml(9002, '1425', currency='IRHT', status='wc-on-hold'),
            _order_xml(9003, '0', status='wc-refunded'),
            _order_xml(9004, '500000'),
            _refund_xml(9100, 9003, '0'),
            _refund_xml(9101, 12345, '10000'),
        ), encoding='utf-8')
        self.raw = OrderFactory(
            wordpress_id=9001, total_price=1965000, is_paid=True,
            first_name='Zivar-Private', last_name='Kasravi-Private', phone_number='09359998877',
            address='Hidden Alley 404',
        )
        self.raw_ht = OrderFactory(wordpress_id=9002, total_price=1425, is_paid=False)
        self.zero = OrderFactory(wordpress_id=9003, total_price=0, is_paid=True)
        self.orphan = OrderFactory(wordpress_id=9999, total_price=777, is_paid=True)
        self.native = OrderFactory(total_price=123456, is_paid=False)

    def _run(self, *args):
        out = io.StringIO()
        call_command('audit_imported_order_amounts', '--export', str(self.export), *args, stdout=out)
        return out.getvalue()

    def _csv_rows(self, path):
        with open(path, encoding='utf-8', newline='') as handle:
            return list(csv.DictReader(handle))

    def _snapshot(self):
        return list(Order.objects.order_by('pk').values_list('pk', 'wordpress_id', 'total_price', 'is_paid', 'status'))

    def test_end_to_end_report(self):
        output = self.dir / 'report.csv'
        stdout = self._run('--output', str(output))
        rows = {(r['record_type'], r['wordpress_id']): r for r in self._csv_rows(output)}

        self.assertEqual(rows[('order', '9001')]['classification'], 'RAW_IRR')
        self.assertEqual(rows[('order', '9002')]['classification'], 'RAW_IRHT')
        self.assertEqual(rows[('order', '9003')]['classification'], 'MATCH')
        self.assertEqual(rows[('order', '9004')]['classification'], 'MISSING_IN_DB')
        self.assertEqual(rows[('order', '9999')]['classification'], 'MISSING_IN_EXPORT')
        self.assertEqual(rows[('refund', '9101')]['flags'], 'REFUND_WITHOUT_PARENT')
        self.assertNotIn(('refund', '9100'), rows)
        self.assertNotIn(str(self.native.pk), {r['wordpress_id'] for r in rows.values()})
        self.assertNotIn('123456', {r['stored_total'] for r in rows.values()})
        self.assertIn('Source export (WXR) findings', stdout)
        self.assertIn('Database observations', stdout)
        self.assertIn('provisional', stdout)

    def test_report_contains_no_personal_data(self):
        output = self.dir / 'report.csv'
        stdout = self._run('--output', str(output))
        content = output.read_text(encoding='utf-8')
        self.assertEqual(content.splitlines()[0], ','.join(CSV_COLUMNS))
        db_fields = (self.raw.first_name, self.raw.last_name, self.raw.phone_number, self.raw.address)
        for secret in PII + db_fields:
            self.assertNotIn(secret, content)
            self.assertNotIn(secret, stdout)

    def test_command_is_read_only(self):
        before = self._snapshot()
        with CaptureQueriesContext(connection) as ctx:
            self._run('--output', str(self.dir / 'report.csv'))
        statements = [q['sql'].lstrip().upper() for q in ctx.captured_queries]
        self.assertTrue(statements)
        self.assertTrue(all(sql.startswith('SELECT') for sql in statements), statements)
        self.assertEqual(self._snapshot(), before)

    def test_skip_db_issues_no_queries(self):
        with CaptureQueriesContext(connection) as ctx:
            stdout = self._run('--skip-db')
        self.assertEqual(len(ctx.captured_queries), 0)
        self.assertIn('not inspected', stdout)
        self.assertIn('NOT_COMPARED', stdout)

    def test_repeated_runs_are_identical(self):
        first, second = self.dir / 'a.csv', self.dir / 'b.csv'
        out1 = self._run('--output', str(first))
        out2 = self._run('--output', str(second))
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(out1.replace(str(first), ''), out2.replace(str(second), ''))

    def test_missing_export(self):
        output = self.dir / 'report.csv'
        with self.assertRaisesMessage(CommandError, 'Reconciliation cannot be completed'):
            call_command('audit_imported_order_amounts', '--export', str(self.dir / 'nope.xml'),
                         '--output', str(output), stdout=io.StringIO())
        self.assertFalse(output.exists())

    def test_malformed_and_empty_exports(self):
        bad = self.dir / 'bad.xml'
        bad.write_text('<rss><channel><item>', encoding='utf-8')
        empty = self.dir / 'empty.xml'
        empty.write_text(_wxr(), encoding='utf-8')
        for path in (bad, empty):
            with self.subTest(path=path.name), self.assertRaisesMessage(CommandError, 'cannot be completed'):
                call_command('audit_imported_order_amounts', '--export', str(path), stdout=io.StringIO())

    def test_existing_output_is_not_overwritten_by_default(self):
        output = self.dir / 'report.csv'
        output.write_text('keep me', encoding='utf-8')
        with self.assertRaises(CommandError):
            self._run('--output', str(output))
        self.assertEqual(output.read_text(encoding='utf-8'), 'keep me')
        self._run('--output', str(output), '--overwrite')
        self.assertIn('classification', output.read_text(encoding='utf-8'))

    def test_invalid_threshold(self):
        with self.assertRaises(CommandError):
            self._run('--wholesale-threshold', 'abc')

    def test_csv_escaping(self):
        self.export.write_text(_wxr(
            _order_xml(9001, '1965000', status='wc-"odd",status\nline'),
            _order_xml(9002, '1425', currency='=HYPERLINK("http://x")'),
            _order_xml(9003, '-5'),
        ), encoding='utf-8')
        output = self.dir / 'report.csv'
        self._run('--output', str(output))
        rows = {r['wordpress_id']: r for r in self._csv_rows(output) if r['record_type'] == 'order'}

        self.assertEqual(rows['9001']['source_status'], 'wc-"odd",status\nline')
        self.assertEqual(rows['9002']['source_currency'], '\'=HYPERLINK("http://x")')
        self.assertEqual(rows['9002']['classification'], 'SOURCE_INVALID')
        self.assertEqual(rows['9003']['source_amount'], "'-5")
        self.assertEqual(rows['9001']['discrepancy'], str(1965000 - 196500))


@skipUnless(connection.vendor == 'postgresql', 'READ ONLY transaction guard is PostgreSQL-specific')
class ReadOnlyTransactionTest(TransactionTestCase):
    def test_reads_inside_read_only_transaction(self):
        OrderFactory(wordpress_id=1, total_price=10)
        OrderFactory(total_price=20)
        with CaptureQueriesContext(connection) as ctx:
            rows = read_imported_totals()
        self.assertEqual(rows, [(1, 10)])
        self.assertIn('SET TRANSACTION READ ONLY', [q['sql'] for q in ctx.captured_queries])
