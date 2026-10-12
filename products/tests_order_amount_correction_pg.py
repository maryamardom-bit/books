"""
PostgreSQL transaction semantics of the correction workflow (finding F6).

These tests need a real PostgreSQL server and a second connection; they must only be run against
the disposable server verified by config.test_runner (config.settings_isolated_test).
"""

import io
import time
from contextlib import contextmanager
from unittest import mock, skipUnless

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DEFAULT_DB_ALIAS, DatabaseError, connection, connections, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from orders.models import Order
from payment.models import Payment
from products.management.commands import correct_imported_order_amounts as correction
from products.management.commands import import_wordpress_complete as importer
from products.tests_import_orders import _order as _import_order
from products.tests_import_orders import _wxr as _import_wxr
from products.tests_order_amount_audit import _order_xml
from products.tests_order_amount_correction import CorrectionFixtureMixin

POSTGRES = connection.vendor == 'postgresql'


@contextmanager
def second_connection():
    default = connections[DEFAULT_DB_ALIAS]
    other = type(default)(dict(default.settings_dict), alias='p0_2_second')
    try:
        yield other
    finally:
        other.close()


def _pgcode(exc):
    return getattr(exc.__cause__, 'pgcode', None)


@skipUnless(POSTGRES, 'PostgreSQL-specific transaction semantics')
class PostgresSemanticsTest(CorrectionFixtureMixin, TransactionTestCase):

    def _totals(self, *wp_ids):
        return {o.wordpress_id: o.total_price for o in Order.objects.filter(wordpress_id__in=wp_ids)}

    def test_server_is_the_disposable_one(self):
        cluster = getattr(settings, 'DISPOSABLE_CLUSTER_NAME', None)
        self.assertIsNotNone(cluster, 'run with config.settings_isolated_test')
        identity = correction.database_identity(connection.alias)
        self.assertEqual(identity['cluster_name'], cluster)
        self.assertTrue(identity['system_identifier'].isdigit())
        self.assertTrue(identity['database_name'].startswith('test_'))

    # -- read-only snapshot

    def test_reads_run_in_a_repeatable_read_read_only_transaction(self):
        with correction.read_only(connection.alias):
            with connection.cursor() as cursor:
                cursor.execute('SHOW transaction_isolation')
                isolation = cursor.fetchone()[0]
                cursor.execute('SHOW transaction_read_only')
                read_only = cursor.fetchone()[0]
            with self.assertRaises(DatabaseError) as ctx:
                with transaction.atomic():
                    Order.objects.update(total_price=1)
        self.assertEqual((isolation, read_only), ('repeatable read', 'on'))
        self.assertEqual(_pgcode(ctx.exception), '25006')
        self.assertEqual(self._totals(101), {101: 1965000})

    def test_set_transaction_must_be_the_first_statement(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                with self.assertRaises(DatabaseError) as ctx:
                    with transaction.atomic():
                        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        self.assertEqual(_pgcode(ctx.exception), '25001')
        with transaction.atomic():
            with self.assertRaisesMessage(CommandError, 'must not run inside an existing transaction'):
                with correction.read_only(connection.alias):
                    pass
            with self.assertRaisesMessage(CommandError, 'must not run inside an existing transaction'):
                with correction.write_transaction(connection.alias, {}):
                    pass

    # -- write transaction

    def test_write_transaction_is_repeatable_read_holds_the_lock_and_row_locks(self):
        approval, sha = self._ready_to_apply()
        seen = {}
        real = correction.Command._lock_rows

        def observe(using, ids):
            real(using, ids)
            with connection.cursor() as cursor:
                cursor.execute('SHOW transaction_isolation')
                seen['isolation'] = cursor.fetchone()[0]
            with second_connection() as other, other.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_lock(%s)', [correction.ADVISORY_LOCK_KEY])
                seen['lock_free_elsewhere'] = cursor.fetchone()[0]
                cursor.execute("SET lock_timeout = '200ms'")
                try:
                    cursor.execute('UPDATE orders_order SET total_price = total_price WHERE id = %s', [ids[0]])
                except DatabaseError as exc:
                    seen['concurrent_update'] = _pgcode(exc)

        with mock.patch.object(correction.Command, '_lock_rows', staticmethod(observe)):
            with CaptureQueriesContext(connection) as ctx:
                self._apply(approval, sha)
        self.assertEqual(seen, {'isolation': 'repeatable read', 'lock_free_elsewhere': False, 'concurrent_update': '55P03'})
        statements = [q['sql'] for q in ctx.captured_queries]
        start = statements.index('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        self.assertIn('pg_try_advisory_xact_lock', statements[start + 1])
        self.assertTrue(any('FOR UPDATE NOWAIT' in s for s in statements[start:]))
        self.assertEqual(self._totals(101, 115), {101: 196500, 115: 200000})
        with second_connection() as other, other.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [correction.ADVISORY_LOCK_KEY])
            self.assertTrue(cursor.fetchone()[0], 'the transaction-level lock must be released at commit')

    def test_advisory_lock_held_elsewhere_refuses_apply_and_rollback(self):
        approval, sha = self._ready_to_apply()
        with second_connection() as other, other.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(%s)', [correction.ADVISORY_LOCK_KEY])
            with self.assertRaisesMessage(CommandError, 'holds the advisory lock'):
                self._apply(approval, sha)
            self.assertEqual(self._rows('execution.csv')[-1]['status'], 'RUN_ROLLED_BACK')
            cursor.execute('SELECT pg_advisory_unlock(%s)', [correction.ADVISORY_LOCK_KEY])
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})
        self._apply(approval, sha, report='second.csv')
        with second_connection() as other, other.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(%s)', [correction.ADVISORY_LOCK_KEY])
            with self.assertRaisesMessage(CommandError, 'holds the advisory lock'):
                self._rollback(approval, sha, execution='second.csv')
        self.assertEqual(self._totals(101, 115), {101: 196500, 115: 200000})

    def test_order_import_is_refused_while_the_correction_lock_is_held(self):
        shop = self.dir / 'shop'
        shop.mkdir()
        (shop / 'shop_order.xml').write_text(_import_wxr(_import_order(7001, '1000', 'IRR')), encoding='utf-8')
        with second_connection() as other, other.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(%s)', [correction.ADVISORY_LOCK_KEY])
            with self.assertRaisesMessage(CommandError, 'order import refused'):
                call_command('import_wordpress_complete', '--dir', str(shop), '--only-orders', stdout=io.StringIO())
            self.assertFalse(Order.objects.filter(wordpress_id=7001).exists())
            cursor.execute('SELECT pg_advisory_unlock(%s)', [correction.ADVISORY_LOCK_KEY])
        call_command('import_wordpress_complete', '--dir', str(shop), '--only-orders', stdout=io.StringIO())
        self.assertTrue(Order.objects.filter(wordpress_id=7001).exists())
        with second_connection() as other, other.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [correction.ADVISORY_LOCK_KEY])
            self.assertTrue(cursor.fetchone()[0], 'the importer must release its session lock')

    def test_importer_holds_the_correction_lock_for_the_whole_order_import(self):
        shop = self.dir / 'shop'
        shop.mkdir()
        (shop / 'shop_order.xml').write_text(_import_wxr(_import_order(7001, '1000', 'IRR')), encoding='utf-8')
        real = importer.Command._import_order_items
        seen = []

        def observe(command, path, report):
            with second_connection() as other, other.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_xact_lock(%s)', [correction.ADVISORY_LOCK_KEY])
                seen.append(cursor.fetchone()[0])
            return real(command, path, report)

        with mock.patch.object(importer.Command, '_import_order_items', observe):
            call_command('import_wordpress_complete', '--dir', str(shop), '--only-orders', stdout=io.StringIO())
        self.assertEqual(seen, [False])

    def test_row_locked_elsewhere_fails_immediately(self):
        approval, sha = self._ready_to_apply()
        with second_connection() as other:
            other.set_autocommit(False)
            with other.cursor() as cursor:
                cursor.execute('SELECT id FROM orders_order WHERE id = %s FOR UPDATE', [self.orders[115].pk])
            started = time.monotonic()
            with self.assertRaisesMessage(CommandError, 'locked by another transaction (NOWAIT)'):
                self._apply(approval, sha)
            elapsed = time.monotonic() - started
            other.rollback()
            other.set_autocommit(True)
        self.assertLess(elapsed, 10)
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    def test_commit_by_another_session_after_the_snapshot_is_a_serialization_failure(self):
        approval, sha = self._ready_to_apply()
        real = correction.Command._lock_rows

        def concurrent_commit_first(using, ids):
            with second_connection() as other, other.cursor() as cursor:
                cursor.execute('UPDATE orders_order SET total_price = total_price WHERE id = %s', [ids[-1]])
            return real(using, ids)

        with mock.patch.object(correction.Command, '_lock_rows', staticmethod(concurrent_commit_first)):
            with self.assertRaisesMessage(CommandError, 'serialization failure'):
                self._apply(approval, sha)
        self.assertEqual(self._rows('execution.csv')[-1]['status'], 'RUN_ROLLED_BACK')
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    def test_payment_committed_after_the_read_is_caught_inside_the_write_transaction(self):
        approval, sha = self._ready_to_apply()
        real = correction.Command._read_current

        def read_then_pay(command, using, expected_identity=None):
            result = real(command, using, expected_identity)
            Payment.objects.create(order=self.orders[101], gateway='sep', amount=1, status=Payment.Status.FAILED)
            return result

        with mock.patch.object(correction.Command, '_read_current', read_then_pay):
            with self.assertRaisesMessage(CommandError, 'A payment record exists for a target order'):
                self._apply(approval, sha)
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    def test_real_commit_time_failure_is_reported_as_unknown(self):
        approval, sha = self._ready_to_apply()
        real = correction.Command._execute

        def execute_then_break_commit(command, using, targets):
            real(command, using, targets)
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO orders_orderitem (order_id, quantity, price, title) VALUES (%s, 1, 1, '')", [2 ** 40])

        with mock.patch.object(correction.Command, '_execute', execute_then_break_commit):
            with self.assertRaisesMessage(CommandError, 'commit outcome unknown (IntegrityError 23503)'):
                self._apply(approval, sha)
        self.assertEqual(self._rows('execution.csv')[-1]['status'], 'RUN_COMMIT_UNKNOWN')
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})
        self._preview('after.csv', 'R1A')
        self.assertEqual({self._by_wp('after.csv')[wp]['category'] for wp in (101, 115)}, {'PROPOSED'})

    def test_large_identifier_lists_are_locked_updated_and_restored_in_chunks(self):
        count = 6000
        user = self.orders[101].user
        Order.objects.bulk_create([
            Order(wordpress_id=20000 + i, total_price=(i + 1) * 1000, is_paid=True, user=user,
                  first_name='x', last_name='x', phone_number='0', address='x')
            for i in range(count)
        ])
        self._write_export(*[_order_xml(20000 + i, str((i + 1) * 1000), 'IRR', 'wc-completed') for i in range(count)])
        approval, sha = self._ready_to_apply()
        with CaptureQueriesContext(connection) as ctx:
            out = self._apply(approval, sha)
        self.assertIn(f'R1A: {count + 2} corrections committed', out)
        lock_queries = [q for q in ctx.captured_queries if 'FOR UPDATE NOWAIT' in q['sql']]
        self.assertEqual(len(lock_queries), -(-(count + 2) // correction.ID_CHUNK))
        stored = dict(Order.objects.filter(wordpress_id__gte=20000).values_list('wordpress_id', 'total_price'))
        self.assertEqual(stored, {20000 + i: (i + 1) * 100 for i in range(count)})

        self._rollback(approval, sha)
        stored = dict(Order.objects.filter(wordpress_id__gte=20000).values_list('wordpress_id', 'total_price'))
        self.assertEqual(stored, {20000 + i: (i + 1) * 1000 for i in range(count)})
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    # -- schema

    def test_required_migrations_are_applied_and_columns_have_the_expected_types(self):
        with correction.read_only(connection.alias):
            correction.check_schema(connection.alias)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT table_name, column_name, data_type FROM information_schema.columns "
                    "WHERE (table_name, column_name) IN (('orders_order', 'total_price'), ('orders_order', 'wordpress_id'), "
                    "('payment_payment', 'order_id'), ('payment_payment', 'amount')) ORDER BY 1, 2"
                )
                columns = cursor.fetchall()
        self.assertEqual(columns, [
            ('orders_order', 'total_price', 'bigint'), ('orders_order', 'wordpress_id', 'integer'),
            ('payment_payment', 'amount', 'bigint'), ('payment_payment', 'order_id', 'bigint'),
        ])

    def test_unapplied_migrations_block_apply(self):
        approval, sha = self._ready_to_apply()
        fake = mock.Mock(app_label='payment')
        fake.name = '0001_initial'
        with mock.patch('django.db.migrations.executor.MigrationExecutor.migration_plan', return_value=[(fake, False)]):
            with self.assertRaisesMessage(CommandError, 'Unapplied migrations required by the correction: payment.0001_initial'):
                self._apply(approval, sha)
        self.assertEqual(self._totals(101), {101: 1965000})
