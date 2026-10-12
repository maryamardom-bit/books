import csv
import io
import tempfile
from pathlib import Path
from unittest import mock
from xml.sax.saxutils import escape

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from orders.factories import OrderFactory
from orders.models import Order
from products.management.commands import import_wordpress_complete as importer
from products.models import DiscountCode, Product

PII = ('Parisa-Private', 'Rahimi-Private', 'parisa.private@example.com', '09127776655', 'Secret Lane 9')


def _order(wp_id, total='1965000', currency='IRR', status='wc-completed', method='sep_gateway',
           first=PII[0], note='Payment ok', date='2026-03-01 10:00:00', post_type='shop_order', email=PII[2]):
    metas = {
        '_order_total': total,
        '_order_currency': currency,
        '_payment_method': method,
        '_billing_first_name': first,
        '_billing_last_name': PII[1],
        '_billing_email': email,
        '_billing_phone': PII[3],
        '_billing_address_1': PII[4],
    }
    meta_xml = ''.join(
        f'<wp:postmeta><wp:meta_key>{k}</wp:meta_key><wp:meta_value>{escape(str(v))}</wp:meta_value></wp:postmeta>'
        for k, v in metas.items() if v is not None
    )
    return (
        f'<item><wp:post_id>{escape(str(wp_id))}</wp:post_id><wp:post_date>{date}</wp:post_date>'
        f'<wp:post_type>{post_type}</wp:post_type><wp:status>{status}</wp:status>{meta_xml}'
        f'<wp:comment><wp:comment_content>{escape(note)}</wp:comment_content></wp:comment></item>'
    )


def _wxr(*items):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:wp="http://wordpress.org/export/1.2/"><channel>'
        + ''.join(items) + '</channel></rss>'
    )


class ImportTestMixin:
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.export = self.dir / 'shop_order.xml'

    def _write(self, *items):
        self.export.write_text(_wxr(*items), encoding='utf-8')

    def _import(self, report_name=None, *extra):
        out, err = io.StringIO(), io.StringIO()
        args = ['import_wordpress_complete', '--dir', str(self.dir), *extra]
        if report_name:
            args += ['--conflict-report', str(self.dir / report_name)]
        call_command(*args, stdout=out, stderr=err)
        self.last_stderr = err.getvalue()
        return out.getvalue()

    def _conflicts(self, report_name):
        with open(self.dir / report_name, encoding='utf-8', newline='') as handle:
            return list(csv.DictReader(handle))

    def _snapshot(self):
        return list(Order.objects.order_by('pk').values_list(
            'pk', 'wordpress_id', 'user_id', 'total_price', 'is_paid', 'status', 'first_name', 'last_name',
            'phone_number', 'address', 'order_notes', 'payment_method', 'datetime_created',
        ))


class ImporterOrderSafetyTest(ImportTestMixin, TestCase):

    def test_first_import_creates_orders_with_raw_source_totals(self):
        self._write(
            _order(101, '1965000', 'IRR', 'wc-completed'),
            _order(102, '1425', 'IRHT', 'wc-on-hold', method='bacs'),
            _order(103, '0', 'IRR', 'wc-refunded'),
            _order(104, '9007199254740993', 'IRR', 'wc-cancelled', method='installment_plan'),
        )
        out = self._import()
        orders = {o.wordpress_id: o for o in Order.objects.all()}

        self.assertIn('new=4 updated=0 skipped=0 conflicts=0', out)
        self.assertEqual(orders[101].total_price, 1965000)
        self.assertEqual(orders[102].total_price, 1425)
        self.assertEqual(orders[103].total_price, 0)
        self.assertEqual(orders[104].total_price, 9007199254740993)
        self.assertEqual([orders[i].is_paid for i in (101, 102, 103, 104)], [True, False, True, False])
        self.assertEqual(orders[104].payment_method, 'installment')
        self.assertEqual(orders[101].first_name, PII[0])
        self.assertEqual(orders[101].phone_number, PII[3])
        self.assertEqual(orders[101].order_notes, 'Payment ok')
        self.assertEqual(orders[101].datetime_created.date().isoformat(), '2026-03-01')
        self.assertEqual(orders[101].status, Order.Status.PENDING_PAYMENT)
        self.assertTrue(orders[101].is_imported)

    def test_repeated_import_is_idempotent_and_never_writes_financial_fields(self):
        self._write(_order(101), _order(102, '1425', 'IRHT', 'wc-on-hold'))
        native = OrderFactory(total_price=50000, is_paid=False)
        self._import()
        before = self._snapshot()

        with CaptureQueriesContext(connection) as ctx:
            out = self._import()
        order_updates = [q['sql'] for q in ctx.captured_queries
                         if q['sql'].lstrip().upper().startswith('UPDATE') and 'orders_order' in q['sql']]

        self.assertIn('new=0 updated=2 skipped=0 conflicts=0', out)
        self.assertEqual(self._snapshot(), before)
        self.assertTrue(order_updates)
        for sql in order_updates:
            self.assertNotIn('"total_price"', sql)
            self.assertNotIn('"is_paid"', sql)
        native.refresh_from_db()
        self.assertEqual((native.total_price, native.is_paid, native.wordpress_id), (50000, False, None))

    def test_repeated_import_refreshes_notes_method_and_date_but_keeps_contact_fields(self):
        self._write(_order(101))
        self._import()
        self._write(_order(101, first='Renamed', note='Shipped', method='installment', date='2026-03-02 08:00:00'))
        out = self._import('conflicts.csv')
        order = Order.objects.get(wordpress_id=101)
        rows = self._conflicts('conflicts.csv')

        self.assertIn('new=0 updated=1 skipped=0 conflicts=1', out)
        self.assertEqual(order.first_name, PII[0])
        self.assertEqual(order.order_notes, 'Shipped')
        self.assertEqual(order.payment_method, 'installment')
        self.assertEqual(order.datetime_created.date().isoformat(), '2026-03-02')
        self.assertEqual(order.total_price, 1965000)
        self.assertEqual([(r['reason'], r['field'], r['stored_value'], r['source_value']) for r in rows],
                         [('CONTACT_CONFLICT', 'first_name', '', '')])

    def test_changed_source_total_is_reported_not_applied(self):
        self._write(_order(101, '1965000'))
        self._import()
        self._write(_order(101, '2500000'))
        out = self._import('conflicts.csv')
        rows = self._conflicts('conflicts.csv')

        self.assertEqual(Order.objects.get(wordpress_id=101).total_price, 1965000)
        self.assertIn('TOTAL_CONFLICT: 1', out)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['wordpress_id'], '101')
        self.assertEqual(rows[0]['reason'], 'TOTAL_CONFLICT')
        self.assertEqual(rows[0]['field'], 'total_price')
        self.assertEqual(rows[0]['stored_value'], '1965000')
        self.assertEqual(rows[0]['source_value'], '2500000')
        self.assertEqual(rows[0]['source_currency'], 'IRR')
        self.assertEqual(rows[0]['action'], 'STORED_PRESERVED')
        self.assertTrue(rows[0]['recommended_action'])

    def test_corrected_existing_totals_are_preserved(self):
        self._write(_order(101, '1965000', 'IRR'), _order(102, '1425', 'IRHT'), _order(103, '1965000', 'IRR'))
        self._import()
        Order.objects.filter(wordpress_id=101).update(total_price=196500)
        Order.objects.filter(wordpress_id=102).update(total_price=1425000)
        Order.objects.filter(wordpress_id=103).update(total_price=180000)

        self._import('conflicts.csv')
        stored = dict(Order.objects.values_list('wordpress_id', 'total_price'))
        reasons = {int(r['wordpress_id']): r['reason'] for r in self._conflicts('conflicts.csv')}

        self.assertEqual(stored, {101: 196500, 102: 1425000, 103: 180000})
        self.assertEqual(reasons, {
            101: 'STORED_EQUALS_PROVISIONAL_CONVERSION',
            102: 'STORED_EQUALS_PROVISIONAL_CONVERSION',
            103: 'TOTAL_CONFLICT',
        })
        advice = {r['recommended_action'] for r in self._conflicts('conflicts.csv') if r['wordpress_id'] == '101'}.pop()
        self.assertIn('not evidence of approval', advice)
        self.assertNotIn('correction log', advice)
        self.assertNotIn('likely an applied correction', advice)

    def test_corrected_paid_flag_is_preserved(self):
        self._write(_order(101, status='wc-completed'), _order(102, status='wc-cancelled'))
        self._import()
        Order.objects.filter(wordpress_id=101).update(is_paid=False)
        self._write(_order(101, status='wc-completed'), _order(102, status='wc-refunded'))

        self._import('conflicts.csv')
        rows = {(r['wordpress_id'], r['field']): r for r in self._conflicts('conflicts.csv')}

        self.assertFalse(Order.objects.get(wordpress_id=101).is_paid)
        self.assertFalse(Order.objects.get(wordpress_id=102).is_paid)
        self.assertEqual(rows[('101', 'is_paid')]['reason'], 'IS_PAID_CONFLICT')
        self.assertEqual(rows[('101', 'is_paid')]['stored_value'], 'False')
        self.assertEqual(rows[('101', 'is_paid')]['source_value'], 'wc-completed')
        self.assertEqual(rows[('102', 'is_paid')]['source_value'], 'wc-refunded')

    def test_invalid_source_totals_do_not_create_orders(self):
        self._write(
            _order(101, ''), _order(102, 'abc'), _order(103, '-5'), _order(104, '10.5'),
            _order(105, '1,000'), _order(106, 'NaN'), _order(107, '1965000'),
        )
        out = self._import('conflicts.csv')
        rows = {r['wordpress_id']: r for r in self._conflicts('conflicts.csv')}

        self.assertEqual(list(Order.objects.values_list('wordpress_id', flat=True)), [107])
        self.assertIn('new=1 updated=0 skipped=6 conflicts=6', out)
        for wp_id in ('101', '102', '103', '105', '106'):
            self.assertEqual(rows[wp_id]['reason'], 'SOURCE_TOTAL_INVALID')
            self.assertEqual(rows[wp_id]['action'], 'NOT_CREATED')
        self.assertEqual(rows['104']['reason'], 'SOURCE_TOTAL_NOT_INTEGER')
        self.assertEqual(rows['103']['source_value'], "'-5")

    def test_invalid_source_total_on_existing_order_preserves_stored_value(self):
        self._write(_order(101, '1965000'))
        self._import()
        self._write(_order(101, 'garbage', first='Updated'))
        self._import('conflicts.csv')
        order = Order.objects.get(wordpress_id=101)
        rows = self._conflicts('conflicts.csv')

        self.assertEqual(order.total_price, 1965000)
        self.assertEqual(order.first_name, PII[0])
        self.assertEqual([(r['reason'], r['action']) for r in rows],
                         [('CONTACT_CONFLICT', 'STORED_PRESERVED'), ('SOURCE_TOTAL_INVALID', 'STORED_PRESERVED')])

    def test_duplicate_source_ids_are_not_imported_or_updated(self):
        self._write(_order(101, '1965000'))
        self._import()
        self._write(
            _order(101, '5000000', first='First copy'),
            _order(101, '6000000', first='Second copy'),
            _order(102, '777', first='Dup new'),
            _order(102, '888', first='Dup new 2'),
            _order(103, '1000'),
        )
        out = self._import('conflicts.csv')
        rows = self._conflicts('conflicts.csv')
        order = Order.objects.get(wordpress_id=101)

        self.assertEqual((order.total_price, order.first_name), (1965000, PII[0]))
        self.assertFalse(Order.objects.filter(wordpress_id=102).exists())
        self.assertTrue(Order.objects.filter(wordpress_id=103).exists())
        self.assertEqual(sorted((r['wordpress_id'], r['reason']) for r in rows),
                         [('101', 'DUPLICATE_SOURCE_ID')] * 2 + [('102', 'DUPLICATE_SOURCE_ID')] * 2)
        self.assertEqual({r['order_id'] for r in rows if r['wordpress_id'] == '101'}, {str(order.pk)})
        self.assertIn('new=1 updated=0 skipped=4 conflicts=4', out)

    def test_invalid_source_ids_are_reported(self):
        self._write(_order('abc'), _order('0'), _order(''), _order(101))
        out = self._import('conflicts.csv')
        rows = self._conflicts('conflicts.csv')

        self.assertEqual(list(Order.objects.values_list('wordpress_id', flat=True)), [101])
        self.assertEqual(sorted(r['wordpress_id'] for r in rows), ['', '0', 'abc'])
        self.assertTrue(all(r['reason'] == 'INVALID_SOURCE_ID' for r in rows))
        self.assertIn('skipped=3', out)

    def test_non_order_items_are_ignored(self):
        self._write(_order(101), _order(201, post_type='shop_order_refund'), _order(301, post_type='product'))
        out = self._import()
        self.assertEqual(list(Order.objects.values_list('wordpress_id', flat=True)), [101])
        self.assertIn('conflicts=0', out)

    def test_conflicts_are_printed_without_report_file(self):
        self._write(_order(101, '1965000'))
        self._import()
        self._write(_order(101, '2000000'))
        out = self._import()
        self.assertIn('Order conflicts (financial fields were not changed):', out)
        self.assertIn('wordpress_id=101 reason=TOTAL_CONFLICT field=total_price stored=1965000 source=2000000', out)

    def test_conflict_report_contains_no_personal_data(self):
        self._write(_order(101, '1965000'), _order(102, 'abc'))
        self._import()
        self._write(_order(101, '2000000'), _order(102, 'abc'))
        out = self._import('conflicts.csv')
        content = (self.dir / 'conflicts.csv').read_text(encoding='utf-8')

        self.assertEqual(content.splitlines()[0],
                         'wordpress_id,order_id,reason,field,stored_value,source_value,source_currency,action,recommended_action')
        for secret in PII + ('Payment ok',):
            self.assertNotIn(secret, content)
            self.assertNotIn(secret, out)

    def test_existing_conflict_report_is_refused_before_importing(self):
        self._write(_order(101))
        (self.dir / 'conflicts.csv').write_text('keep', encoding='utf-8')
        with self.assertRaises(CommandError):
            self._import('conflicts.csv')
        self.assertFalse(Order.objects.exists())
        self.assertEqual((self.dir / 'conflicts.csv').read_text(encoding='utf-8'), 'keep')


def _coupon(code, amount, used, status='publish', dtype='fixed_cart', limit='1', expires=''):
    metas = {'discount_type': dtype, 'coupon_amount': amount, 'usage_limit': limit, 'usage_count': used, 'date_expires': expires}
    meta_xml = ''.join(
        f'<wp:postmeta><wp:meta_key>{k}</wp:meta_key><wp:meta_value>{v}</wp:meta_value></wp:postmeta>'
        for k, v in metas.items()
    )
    return (f'<item><title>{code}</title><wp:post_type>shop_coupon</wp:post_type>'
            f'<wp:status>{status}</wp:status>{meta_xml}</item>')


class ImporterHazardTest(ImportTestMixin, TestCase):
    """Code-only fixes for importer re-run hazards (no real data is involved)."""

    def test_invalid_date_on_existing_order_keeps_the_stored_date(self):
        self._write(_order(101, date='2019-05-01 10:00:00'))
        self._import()
        stored = Order.objects.get(wordpress_id=101).datetime_created
        self.assertEqual(stored.year, 2019)
        for bad in ('', 'not-a-date', '0000-00-00 00:00:00'):
            with self.subTest(date=bad):
                self._write(_order(101, date=bad))
                name = f'conflicts-{len(bad)}.csv'
                self._import(name)
                order = Order.objects.get(wordpress_id=101)
                self.assertEqual(order.datetime_created, stored)
                self.assertEqual([(r['reason'], r['action']) for r in self._conflicts(name)],
                                 [('SOURCE_DATE_INVALID', 'STORED_PRESERVED')])

    def test_invalid_date_on_new_order_is_not_created(self):
        self._write(_order(101, date='garbage'), _order(102))
        out = self._import('conflicts.csv')
        self.assertEqual(list(Order.objects.values_list('wordpress_id', flat=True)), [102])
        self.assertIn('new=1 updated=0 skipped=1', out)
        self.assertEqual([(r['wordpress_id'], r['reason'], r['action']) for r in self._conflicts('conflicts.csv')],
                         [('101', 'SOURCE_DATE_INVALID', 'NOT_CREATED')])

    def test_existing_order_owner_and_contact_fields_are_kept_and_reported_without_values(self):
        self._write(_order(101))
        self._import()
        order = Order.objects.get(wordpress_id=101)
        owner_id, users = order.user_id, get_user_model().objects.count()
        other = get_user_model().objects.create_user(username='other', email='someone.else@example.com')
        self._write(_order(101, email=other.email, first='New-Name-Private'))

        out = self._import('conflicts.csv')
        order.refresh_from_db()
        rows = self._conflicts('conflicts.csv')
        content = (self.dir / 'conflicts.csv').read_text(encoding='utf-8')

        self.assertEqual(order.user_id, owner_id)
        self.assertEqual(order.first_name, PII[0])
        self.assertEqual(get_user_model().objects.count(), users + 1)
        self.assertEqual(sorted((r['reason'], r['field']) for r in rows),
                         [('CONTACT_CONFLICT', 'first_name'), ('OWNERSHIP_CONFLICT', 'user')])
        for secret in (other.email, 'New-Name-Private', PII[0], PII[2]):
            self.assertNotIn(secret, content)
            self.assertNotIn(secret, out)

    def test_write_error_rolls_back_the_order_and_hides_the_exception_message(self):
        self._write(_order(101, note='old note'))
        self._import()
        order = Order.objects.get(wordpress_id=101)
        self._write(_order(101, note='new note', first='Changed'))

        with mock.patch.object(importer.Command, '_compare_financials', side_effect=ValueError(f'boom {PII[2]}')):
            out = self._import('conflicts.csv')
        order.refresh_from_db()
        rows = self._conflicts('conflicts.csv')

        self.assertEqual(order.order_notes, 'old note')
        self.assertEqual([(r['reason'], r['order_id'], r['source_value']) for r in rows],
                         [('WRITE_ERROR', str(order.pk), 'ValueError')])
        self.assertIn('! order 101: ValueError', self.last_stderr)
        self.assertNotIn(PII[2], self.last_stderr + out)

    def test_imported_orders_missing_from_the_source_are_reported(self):
        self._write(_order(101), _order(102))
        self._import()
        native = OrderFactory()
        self._write(_order(101))
        self._import('conflicts.csv')
        rows = self._conflicts('conflicts.csv')
        order_102 = Order.objects.get(wordpress_id=102)

        self.assertEqual([(r['wordpress_id'], r['order_id'], r['reason'], r['action']) for r in rows],
                         [('102', str(order_102.pk), 'MISSING_IN_SOURCE', 'NONE')])
        self.assertNotIn(str(native.pk), [r['order_id'] for r in rows])

    def test_unwritable_report_destination_is_refused_before_importing(self):
        self._write(_order(101))
        with self.assertRaises(CommandError):
            self._import('missing-dir/conflicts.csv')
        self.assertFalse(Order.objects.exists())

    def test_interrupted_run_keeps_the_rows_written_so_far(self):
        self._write(_order(101, '1965000'), _order(102))
        self._import()
        self._write(_order(101, '2500000'), _order(102))
        real_apply = importer.Command._apply_order
        calls = []

        def apply_then_interrupt(command, wp_id, source, conflicts):
            calls.append(wp_id)
            if len(calls) == 2:
                raise KeyboardInterrupt
            return real_apply(command, wp_id, source, conflicts)

        with mock.patch.object(importer.Command, '_apply_order', apply_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self._import('conflicts.csv')
        rows = self._conflicts('conflicts.csv')

        self.assertEqual([(r['wordpress_id'], r['reason']) for r in rows],
                         [('101', 'TOTAL_CONFLICT'), ('', 'RUN_INCOMPLETE')])

    def test_only_orders_mode_never_touches_products_coupons_or_the_network(self):
        self._write(_order(101))
        (self.dir / 'product.xml').write_text('not even xml', encoding='utf-8')
        (self.dir / 'shop_coupon.xml').write_text('not even xml', encoding='utf-8')
        (self.dir / 'pages.xml').write_text('not even xml', encoding='utf-8')

        with mock.patch.object(importer, 'call_command') as product_import, \
                mock.patch.object(importer, 'fetch', side_effect=AssertionError('network')) as fetch:
            out = self._import(None, '--only-orders')

        product_import.assert_not_called()
        fetch.assert_not_called()
        self.assertIn('Order transfer finished (orders only).', out)
        self.assertEqual(list(Order.objects.values_list('wordpress_id', flat=True)), [101])
        self.assertFalse(Product.objects.exists())
        self.assertFalse(DiscountCode.objects.exists())

    def test_only_orders_and_skip_orders_are_exclusive(self):
        self._write(_order(101))
        with self.assertRaises(CommandError):
            self._import(None, '--only-orders', '--skip-orders')
        self.assertFalse(Order.objects.exists())

    def test_coupon_reimport_creates_new_codes_and_never_updates_existing_ones(self):
        coupons = self.dir / 'shop_coupon.xml'
        coupons.write_text(_wxr(_coupon('KEEPME', '500000', '0'), _coupon('PCT10', '10', '0', dtype='percent')),
                           encoding='utf-8')
        self.export.unlink(missing_ok=True)
        self._import()
        DiscountCode.objects.filter(code='KEEPME').update(amount=50000, used_count=1, active=False, max_uses=1)
        before = list(DiscountCode.objects.order_by('code').values())
        coupons.write_text(_wxr(
            _coupon('KEEPME', '500000', '0', limit='5'),
            _coupon('PCT10', '15', '3', dtype='percent'),
            _coupon('NEWONE', '100000', '0'),
        ), encoding='utf-8')

        out = self._import()

        after = {c['code']: c for c in DiscountCode.objects.values()}
        self.assertEqual([after[c['code']] for c in before], before)
        self.assertEqual((after['NEWONE']['amount'], after['NEWONE']['used_count']), (100000, 0))
        self.assertIn('Coupons imported: new=1 existing_preserved=2', out)
        self.assertIn('Existing coupons differing from the export (kept as stored): '
                      'active=1 amount=1 max_uses=1 percent=1 used_count=2', out)
        self.assertNotIn('KEEPME', out)
