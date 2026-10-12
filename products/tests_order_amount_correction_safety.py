"""
Phase 4 hardening tests for the order amount correction workflow (findings F1-F5, F7).

Every order is fictitious. Writes need PostgreSQL (the command refuses other targets), so the
classes that apply or roll back are skipped elsewhere; run them with config.settings_isolated_test.
"""

import csv
import hashlib
import io
import json
from decimal import Decimal
from unittest import mock, skipUnless

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DEFAULT_DB_ALIAS, OperationalError, connection, connections
from django.test import SimpleTestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from orders.factories import OrderFactory
from orders.models import Order
from payment.models import Payment
from products.management.commands import correct_imported_order_amounts as correction
from products.management.commands.audit_imported_order_amounts import (
    FLAG_CANCELLED_SEP_ANOMALY,
    FLAG_HAS_REFUND_RECORD,
    FLAG_WHOLESALE_SIZED,
    FLAG_ZERO_TOTAL,
    RAW_IRHT,
    RAW_IRR,
    SourceOrder,
)
from products.tests_import_orders import _order as _import_order
from products.tests_import_orders import _wxr as _import_wxr
from products.tests_order_amount_correction import WRITE_SQL, CorrectionFixtureMixin, classify

POSTGRES = connection.vendor == 'postgresql'
IRR_AND_IRHT = {
    'IRR': {'toman_per_unit': '0.1', 'evidence_ref': 'test fixture'},
    'IRHT': {'toman_per_unit': '1000', 'evidence_ref': 'test fixture'},
}
STATUSES = ('wc-completed', 'wc-on-hold', 'wc-cancelled', 'wc-refunded', 'wc-processing', 'wc-pending', '')
METHODS = ('WC_Sep_Payment_Gateway', 'sep_gateway', 'bacs', 'asanpardakht', '')
THRESHOLDS = ('0', '20000000', '999999999999999999')


class SafetyScenarioMixin(CorrectionFixtureMixin):
    ANOMALY_IDS = frozenset({107, 116})
    SCENARIO = CorrectionFixtureMixin.SCENARIO + [
        (116, '2401625', 'IRHT', 'wc-cancelled', 'bacs', 2401625),     # second anomaly, method changed to bacs
        (117, '40858', 'IRHT', 'wc-completed', 'bacs', 40858),
        (118, '25000', 'IRHT', 'wc-on-hold', 'WC_Sep_Payment_Gateway', 25000),
        (119, '30000', 'IRHT', 'wc-refunded', 'bacs', 30000),
        (120, '900', 'IRHT', 'wc-cancelled', 'bacs', 900),
        (121, '20000', 'IRHT', 'wc-completed', 'bacs', 20000),
        (122, '20001', 'IRHT', 'wc-completed', 'bacs', 20001),
        (123, '74020', 'IRR', 'wc-cancelled', 'bacs', 74020),
    ]

    def _totals(self, *wp_ids):
        return {o.wordpress_id: o.total_price for o in Order.objects.filter(wordpress_id__in=wp_ids)}

    def _approve(self, rule, factors=None, preview=None):
        preview = preview or f'preview-{rule}-{len(list(self.dir.iterdir()))}.csv'
        preview_sha = self._value(self._preview(preview, rule), 'preview_sha256')
        return self._approval(preview_sha, rule=rule, factors=factors)

    def _patch(self, name, value):
        patcher = mock.patch.object(correction, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)


# ---------------------------------------------------------------- F1: anomalies

class AnomalyClassificationTest(SimpleTestCase):

    def test_approved_anomaly_ids_are_excluded_on_every_classification_path(self):
        audits = sorted(correction.KNOWN_CLASSIFICATIONS)
        flag_sets = ([], [FLAG_WHOLESALE_SIZED], [FLAG_CANCELLED_SEP_ANOMALY], [FLAG_HAS_REFUND_RECORD], [FLAG_ZERO_TOTAL])
        amounts = (('4400125', 4400125), ('900', 900), ('20000', 20000), ('0', 0))
        with mock.patch.object(correction, 'APPROVED_ANOMALY_WORDPRESS_IDS', frozenset({7001, 7002})):
            for wp in (7001, 7002):
                for audit in audits:
                    for status in STATUSES:
                        for currency in ('IRR', 'IRHT', 'IRT', ''):
                            for flags in flag_sets:
                                for amount, stored in amounts:
                                    for has_payment in (False, True):
                                        result = classify(audit, status, currency, amount, stored, flags, has_payment, wp)
                                        self.assertEqual(result, ('R7', 'EXCL_R7_APPROVED_ANOMALY_ID', '', ''),
                                                         (wp, audit, status, currency, flags, amount, has_payment))

    def test_cancelled_large_irht_is_never_proposed_whatever_the_method_or_threshold(self):
        for method in METHODS:
            for threshold in THRESHOLDS:
                for wp_id, total in ((1, '4400125'), (2, '2401625')):
                    with self.subTest(method=method, threshold=threshold, wp=wp_id):
                        orders = [SourceOrder(str(wp_id), 'wc-cancelled', 'IRHT', total, method)]
                        current = {10: (wp_id, int(total), False)}
                        [row] = correction.build_before_state(orders, [], current, set(), Decimal(threshold))
                        self.assertNotIn(row['reason_code'], correction.CORRECTION_REASONS.values())
                        self.assertEqual(correction.base_category(row['reason_code']), correction.OWNER_REVIEW)
                        expected = 'EXCL_R7_ANOMALY' if 'sep' in method.lower() else 'REVIEW_LARGE_IRHT'
                        self.assertEqual((row['rule'], row['reason_code']), ('R7' if expected == 'EXCL_R7_ANOMALY' else 'R4', expected))

    def test_anomaly_flag_no_longer_depends_on_the_wholesale_threshold(self):
        orders = [SourceOrder('5', 'wc-cancelled', 'IRHT', '4400125', 'WC_Sep_Payment_Gateway')]
        for threshold in THRESHOLDS:
            with self.subTest(threshold=threshold):
                [row] = correction.build_before_state(orders, [], {1: (5, 4400125, False)}, set(), Decimal(threshold))
                self.assertIn(FLAG_CANCELLED_SEP_ANOMALY, row['flags'])
                self.assertEqual(row['rule'], 'R7')

    def test_policy_hash_covers_ids_threshold_and_limits(self):
        base = correction.policy_sha256(correction.classification_policy())
        for name, value in (
            ('APPROVED_ANOMALY_WORDPRESS_IDS', frozenset({1, 2})),
            ('REVIEWED_WHOLESALE_THRESHOLD', Decimal('1')),
            ('LARGE_IRHT_SOURCE_UNITS', Decimal('1')),
        ):
            with self.subTest(name=name), mock.patch.object(correction, name, value):
                self.assertNotEqual(correction.policy_sha256(correction.classification_policy()), base)

    def test_eligibility_recheck_rejects_rows_that_must_never_be_written(self):
        row = {
            'order_id': 1, 'wordpress_id': 50, 'rule': 'R2', 'reason_code': 'R2_IRHT_X1000', 'flags': '',
            'source_currency': 'IRHT', 'source_amount': '900', 'factor': '1000', 'proposed_after': 900000,
        }
        correction.assert_batch_eligible([row], [1], 'R2')
        cases = {
            'anomaly flag': {'flags': FLAG_CANCELLED_SEP_ANOMALY},
            'large IRHT': {'source_amount': '20001', 'proposed_after': 20001000},
            'factor': {'factor': '100'},
            'value': {'proposed_after': 900001},
            'reason': {'reason_code': 'REVIEW_LARGE_IRHT'},
        }
        for name, change in cases.items():
            with self.subTest(case=name), self.assertRaisesMessage(CommandError, 'not eligible'):
                correction.assert_batch_eligible([{**row, **change}], [1], 'R2')
        with mock.patch.object(correction, 'APPROVED_ANOMALY_WORDPRESS_IDS', frozenset({50})):
            with self.assertRaisesMessage(CommandError, 'not eligible'):
                correction.assert_batch_eligible([row], [1], 'R2')


# ---------------------------------------------------------------- F3: large IRHT

class LargeIrhtClassificationTest(SimpleTestCase):

    def test_large_irht_goes_to_owner_review_for_every_status_method_and_threshold(self):
        expected_rule = {'wc-completed': 'R2', 'wc-on-hold': 'R2', 'wc-cancelled': 'R4', 'wc-refunded': 'R5'}
        for status, rule in expected_rule.items():
            for flags in ([], [FLAG_WHOLESALE_SIZED], [FLAG_HAS_REFUND_RECORD]):
                for amount in ('20001', '40858', '2401625'):
                    with self.subTest(status=status, flags=flags, amount=amount):
                        got = classify(RAW_IRHT, status, 'IRHT', amount, int(amount), flags)
                        got_rule = 'R5' if FLAG_HAS_REFUND_RECORD in flags else rule
                        self.assertEqual(got, (got_rule, 'REVIEW_LARGE_IRHT', '', ''))
                        self.assertEqual(correction.base_category(got[1]), correction.OWNER_REVIEW)
        for method in METHODS:
            for threshold in THRESHOLDS:
                orders = [SourceOrder('9', 'wc-completed', 'IRHT', '40858', method)]
                [row] = correction.build_before_state(orders, [], {1: (9, 40858, True)}, set(), Decimal(threshold))
                self.assertEqual((row['rule'], row['reason_code']), ('R2', 'REVIEW_LARGE_IRHT'))

    def test_limit_is_strict_and_irr_is_unaffected(self):
        self.assertEqual(classify(RAW_IRHT, 'wc-completed', 'IRHT', '20000', 20000), ('R2', 'R2_IRHT_X1000', '1000', 20000000))
        self.assertEqual(classify(RAW_IRHT, 'wc-completed', 'IRHT', '20001', 20001)[1], 'REVIEW_LARGE_IRHT')
        self.assertEqual(classify(RAW_IRR, 'wc-completed', 'IRR', '250000000', 250000000, [FLAG_WHOLESALE_SIZED])[0], 'R1B')


# ---------------------------------------------------------------- command-level tests

@skipUnless(POSTGRES, 'apply and rollback refuse non-PostgreSQL targets')
class AnomalyAndThresholdCommandTest(SafetyScenarioMixin, TransactionTestCase):

    def test_both_known_bypasses_leave_the_anomalies_excluded(self):
        self._snapshot('--wholesale-threshold', '999999999999')
        self._preview('preview.csv', 'R4')
        rows = self._by_wp('preview.csv')
        self.assertEqual({wp: rows[wp]['reason_code'] for wp in (107, 116)},
                         {107: 'EXCL_R7_APPROVED_ANOMALY_ID', 116: 'EXCL_R7_APPROVED_ANOMALY_ID'})
        self.assertEqual({wp for wp, r in rows.items() if r['category'] == 'PROPOSED'}, {120, 123})
        self.assertIn(FLAG_CANCELLED_SEP_ANOMALY, (self.before_state.read_text(encoding='utf-8')))

    def test_without_the_registry_the_bypasses_still_reach_owner_review(self):
        self._patch('APPROVED_ANOMALY_WORDPRESS_IDS', frozenset())
        self._snapshot('--wholesale-threshold', '999999999999')
        self._preview('preview.csv')
        rows = self._by_wp('preview.csv')
        self.assertEqual((rows[107]['category'], rows[107]['reason_code']), ('OWNER_REVIEW', 'EXCL_R7_ANOMALY'))
        self.assertEqual((rows[116]['category'], rows[116]['rule'], rows[116]['reason_code']),
                         ('OWNER_REVIEW', 'R4', 'REVIEW_LARGE_IRHT'))

    def test_apply_refuses_until_the_registry_holds_the_approved_ids(self):
        for ids, message in (
            (frozenset(), 'holds 0 ids'),
            (frozenset({107}), 'holds 1 ids'),
            (frozenset({107, 999}), 'Approved anomaly id 999 is not an R7 row'),
            (frozenset({116, 101}), 'are not in the approved anomaly registry'),
        ):
            with self.subTest(ids=sorted(ids)), mock.patch.object(correction, 'APPROVED_ANOMALY_WORDPRESS_IDS', ids):
                self._snapshot(before_state=self.dir / f'before-{len(list(self.dir.iterdir()))}.csv')
                approval, sha = self._approve('R1A')
                with self.assertRaisesMessage(CommandError, message):
                    self._apply(approval, sha, report=f'exec-{sha[:8]}.csv')
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    def test_apply_refuses_an_unreviewed_threshold(self):
        self._snapshot('--wholesale-threshold', '999999999999')
        approval, sha = self._approve('R4', factors=IRR_AND_IRHT)
        with self.assertRaisesMessage(CommandError, 'only the reviewed value 20000000 may be applied'):
            self._apply(approval, sha, rule='R4')
        self.assertEqual(self._totals(120, 123), {120: 900, 123: 74020})

    def test_policy_change_after_the_snapshot_invalidates_every_artifact(self):
        self._snapshot()
        approval, sha = self._approve('R1A')
        for name, value in (('APPROVED_ANOMALY_WORDPRESS_IDS', frozenset({107, 117})),
                            ('LARGE_IRHT_SOURCE_UNITS', Decimal('50000'))):
            with self.subTest(name=name), mock.patch.object(correction, name, value):
                with self.assertRaisesMessage(CommandError, 'Classification policy changed'):
                    self._preview(f'p-{name}.csv')
                with self.assertRaisesMessage(CommandError, 'Classification policy changed'):
                    self._apply(approval, sha, report=f'e-{name}.csv')

    def test_large_irht_rows_are_visible_in_the_report(self):
        self._snapshot('--wholesale-threshold', '999999999999')
        out = self._preview('preview.csv')
        rows = self._by_wp('preview.csv')
        for wp in (117, 118, 119, 122):
            self.assertEqual((rows[wp]['category'], rows[wp]['reason_code'], rows[wp]['proposed_after']),
                             ('OWNER_REVIEW', 'REVIEW_LARGE_IRHT', ''))
        self.assertEqual((rows[121]['category'], rows[121]['proposed_after']), ('PROPOSED', '20000000'))
        self.assertIn('reason REVIEW_LARGE_IRHT: 4', out)
        self.assertIn('WHOLESALE_THRESHOLD_NOT_REVIEWED', out)


@skipUnless(POSTGRES, 'apply and rollback refuse non-PostgreSQL targets')
class IdentityAndAuthorizationTest(SafetyScenarioMixin, TransactionTestCase):

    def test_before_state_records_a_complete_postgresql_identity(self):
        self._snapshot()
        identity = self._manifest()['database_identity']
        for key in correction.IDENTITY_REQUIRED:
            self.assertTrue(identity[key], key)
        self.assertTrue(identity['system_identifier'].isdigit())
        self.assertEqual(identity['database_name'], connection.settings_dict['NAME'])

    def test_apply_refuses_another_database_or_an_incomplete_identity(self):
        approval, sha = self._ready_to_apply()
        real = correction.database_identity(connection.alias)
        for name, fake in (
            ('other cluster', {**real, 'system_identifier': '1'}),
            ('other database', {**real, 'database_oid': '1'}),
            ('restored copy', {**real, 'database_name': 'restored'}),
            ('no system identifier', {**real, 'system_identifier': None}),
            ('not postgresql', {'vendor': 'sqlite'}),
        ):
            with self.subTest(case=name), mock.patch.object(correction, 'database_identity', return_value=fake):
                with self.assertRaises(CommandError) as ctx:
                    self._apply(approval, sha, report=f'exec-{len(name)}-{name[:3]}.csv')
                self.assertRegex(str(ctx.exception), 'not the database recorded|identity is incomplete|Only a PostgreSQL target')
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    def test_identity_is_checked_again_inside_the_write_transaction(self):
        approval, sha = self._ready_to_apply()
        real = correction.database_identity(connection.alias)
        with mock.patch.object(correction, 'database_identity', side_effect=[real, {**real, 'system_identifier': '1'}]):
            with self.assertRaisesMessage(CommandError, 'not the database recorded'):
                self._apply(approval, sha)
        self.assertEqual(self._rows('execution.csv')[-1]['status'], 'RUN_ROLLED_BACK')
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    def test_a_valid_hash_alone_is_not_authorisation(self):
        approval, sha = self._ready_to_apply()
        correction.AUTHORIZED_APPROVALS.clear()
        with self.assertRaisesMessage(CommandError, 'proves the file is intact, not that the owner approved it'):
            self._apply(approval, sha)
        self.assertFalse((self.dir / 'execution.csv').exists())

    def test_preview_lists_every_blocker_and_an_unsigned_approval_request(self):
        self._snapshot()
        out = self._preview('preview.csv', 'R1A')
        blockers = self._value(out, 'apply_blockers').split(',')
        self.assertIn('EXECUTION_DISABLED_IN_CODE', blockers)
        self.assertNotIn('DATABASE_IDENTITY_NOT_VERIFIED', blockers)
        request = json.loads((self.dir / 'preview.csv.approval-request.json').read_text(encoding='utf-8'))
        self.assertIsNone(request['approval_ref'])
        self.assertEqual(request['currency_factors'], {'IRR': {'toman_per_unit': '0.1', 'evidence_ref': None}})
        self.assertEqual(set(request), correction.APPROVAL_KEYS)
        self.assertEqual(request['database_identity'], self._manifest()['database_identity'])


@skipUnless(POSTGRES, 'apply and rollback refuse non-PostgreSQL targets')
class DriftAndBatchTest(SafetyScenarioMixin, TransactionTestCase):

    def _assert_refused(self, approval, sha, message, rule='R1A'):
        with self.assertRaisesMessage(CommandError, message):
            self._apply(approval, sha, report=f'refused-{len(list(self.dir.iterdir()))}.csv', rule=rule)

    def test_new_imported_order_after_the_snapshot_blocks_every_batch(self):
        approval, sha = self._ready_to_apply()
        OrderFactory(wordpress_id=5000, total_price=10, is_paid=True)
        self._assert_refused(approval, sha, 'NOT_IN_BEFORE_STATE=1')
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    def test_deleted_orders_block_the_batch_even_outside_the_rule(self):
        approval, sha = self._ready_to_apply()
        self.orders[102].delete()
        self._assert_refused(approval, sha, 'DB_ORDER_MISSING=1')
        self.orders[115].delete()
        self._assert_refused(approval, sha, 'DB_ORDER_MISSING=2')
        self.assertEqual(self._totals(101), {101: 1965000})

    def test_changed_source_data_needs_a_fresh_snapshot_and_approval(self):
        approval, sha = self._ready_to_apply()
        first = (self.before_state, self.before_sha)
        self.SCENARIO = [s if s[0] != 101 else (101, '1965010', 'IRR', 'wc-completed', 'sep_gateway', 1965000) for s in self.SCENARIO]
        self._write_export()
        self._snapshot(before_state=self.dir / 'before-2.csv')
        self.assertNotEqual(self.before_sha, first[1])
        self.assertEqual(self._by_before_state()[101]['reason_code'], 'EXCL_R8_MISMATCH')
        self._assert_refused(approval, sha, 'bound to a different before-state')

    def _by_before_state(self):
        with open(self.before_state, encoding='utf-8', newline='') as handle:
            return {int(r['wordpress_id']): r for r in csv.DictReader(handle)}

    def test_sequential_batches_need_fresh_artifacts(self):
        self._snapshot(before_state=self.dir / 'before-1.csv')
        r1a, r1a_sha = self._approve('R1A')
        stale_r1b, stale_r1b_sha = self._approve('R1B')
        self._apply(r1a, r1a_sha, report='exec-r1a.csv')
        self._assert_refused(stale_r1b, stale_r1b_sha, 'rows of other batches were corrected', rule='R1B')
        self.assertEqual(self._totals(102), {102: 250000000})

        self._snapshot(before_state=self.dir / 'before-2.csv')
        self.assertEqual(self._by_before_state()[101]['reason_code'], 'REVIEW_STORED_EQUALS_PROVISIONAL_CONVERSION')
        self._assert_refused(stale_r1b, stale_r1b_sha, 'bound to a different before-state', rule='R1B')
        r1b, r1b_sha = self._approve('R1B')
        out = self._apply(r1b, r1b_sha, report='exec-r1b.csv', rule='R1B')
        self.assertIn('R1B: 1 corrections committed', out)
        self.assertEqual(self._totals(101, 102, 115), {101: 196500, 102: 25000000, 115: 200000})

    def test_mixed_irr_irht_batch_needs_both_factor_approvals(self):
        self._snapshot()
        irr_only, irr_only_sha = self._approve('R4')
        self._assert_refused(irr_only, irr_only_sha, 'Conversion factor for IRHT is not approved', rule='R4')
        self.assertEqual(self._totals(120, 123), {120: 900, 123: 74020})
        preview_sha = json.loads(irr_only.read_text(encoding='utf-8'))['preview_sha256']
        both, both_sha = self._approval(preview_sha, rule='R4', factors=IRR_AND_IRHT)
        self._apply(both, both_sha, rule='R4')
        self.assertEqual(self._totals(104, 107, 116, 120, 123), {104: 74025, 107: 4400125, 116: 2401625, 120: 900000, 123: 7402})
        self.assertEqual({(r['wordpress_id'], r['source_currency'], r['factor']) for r in self._rows('execution.csv') if r['wordpress_id']},
                         {('120', 'IRHT', '1000'), ('123', 'IRR', '0.1')})

    def test_post_update_sum_is_verified_before_commit(self):
        approval, sha = self._ready_to_apply()

        def off_by_one(using, target):
            return Order.objects.filter(pk=target['order_id'], total_price=target['total_price_before']).update(
                total_price=target['proposed_after'] + 1)

        with mock.patch.object(correction.Command, '_compare_and_set', staticmethod(off_by_one)):
            self._assert_refused(approval, sha, 'Post-update sum differs from the preview')
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    def test_importer_rerun_after_a_correction_keeps_corrected_amounts_and_paid_flags(self):
        approval, sha = self._ready_to_apply()
        self._apply(approval, sha)
        before = list(Order.objects.filter(wordpress_id__in=(101, 115)).order_by('pk').values_list('total_price', 'is_paid', 'status'))
        shop = self.dir / 'shop' / 'shop_order.xml'
        shop.parent.mkdir()
        shop.write_text(_import_wxr(
            _import_order(101, '1965000', 'IRR', 'wc-completed'),
            _import_order(115, '2000000', 'IRR', 'wc-on-hold'),
            _import_order(5001, '3000000', 'IRR', 'wc-completed'),
        ), encoding='utf-8')
        call_command('import_wordpress_complete', '--dir', str(shop.parent), '--only-orders', stdout=io.StringIO(), stderr=io.StringIO())

        after = list(Order.objects.filter(wordpress_id__in=(101, 115)).order_by('pk').values_list('total_price', 'is_paid', 'status'))
        self.assertEqual(after, before)
        self.assertEqual(Order.objects.get(wordpress_id=5001).total_price, 3000000)
        with self.assertRaisesMessage(CommandError, 'NOT_IN_BEFORE_STATE=1'):
            self._apply(approval, sha, report='again.csv')


@skipUnless(POSTGRES, 'apply and rollback refuse non-PostgreSQL targets')
class CommitOutcomeTest(SafetyScenarioMixin, TransactionTestCase):

    def test_commit_failure_is_reported_as_unknown_and_never_as_rolled_back(self):
        approval, sha = self._ready_to_apply()
        db = connections[DEFAULT_DB_ALIAS]
        real_commit, real_execute = db.commit, correction.Command._execute
        executed = []

        def fail_after_execute():
            if executed:
                raise OperationalError('simulated commit failure')
            return real_commit()

        def execute(command, using, targets):
            real_execute(command, using, targets)
            executed.append(True)

        with mock.patch.object(db, 'commit', side_effect=fail_after_execute), \
                mock.patch.object(correction.Command, '_execute', execute):
            with self.assertRaisesMessage(CommandError, 'commit outcome unknown (OperationalError)'):
                self._apply(approval, sha)
        self.assertEqual([r['status'] for r in self._rows('execution.csv')][-2:], ['RUN_STARTED', 'RUN_COMMIT_UNKNOWN'])
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

        out = self._rollback(approval, sha)
        self.assertIn('Nothing to roll back (RUN_COMMIT_UNKNOWN)', out)
        self._apply(approval, sha, report='retry.csv')
        self.assertEqual(self._totals(101, 115), {101: 196500, 115: 200000})

    def test_interruption_in_the_transaction_rolls_back_and_says_so(self):
        approval, sha = self._ready_to_apply()
        real = correction.Command._compare_and_set
        calls = []

        def interrupt_second(using, target):
            calls.append(target)
            if len(calls) == 2:
                raise KeyboardInterrupt
            return real(using, target)

        with mock.patch.object(correction.Command, '_compare_and_set', staticmethod(interrupt_second)):
            with self.assertRaises(KeyboardInterrupt):
                self._apply(approval, sha)
        self.assertEqual([r['status'] for r in self._rows('execution.csv')],
                         ['INTENDED', 'INTENDED', 'RUN_STARTED', 'RUN_ROLLED_BACK'])
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})

    def test_a_report_cut_off_after_run_started_is_resolved_from_the_database(self):
        approval, sha = self._ready_to_apply()
        self._apply(approval, sha)
        lines = (self.dir / 'execution.csv').read_text(encoding='utf-8').splitlines(keepends=True)
        (self.dir / 'killed.csv').write_text(''.join(lines[:-1]), encoding='utf-8')
        self.assertTrue(lines[-2].startswith('RUN_STARTED'))

        out = self._rollback(approval, sha, execution='killed.csv')
        self.assertIn('2 orders restored', out)
        self.assertEqual(self._totals(101, 115), {101: 1965000, 115: 2000000})
        self.assertIn('Nothing to roll back (RUN_STARTED)', self._rollback(approval, sha, execution='killed.csv', report='again.csv'))


# ---------------------------------------------------------------- F2: rollback

@skipUnless(POSTGRES, 'apply and rollback refuse non-PostgreSQL targets')
class RollbackTest(SafetyScenarioMixin, TransactionTestCase):

    FIELDS = ('pk', 'wordpress_id', 'total_price', 'is_paid', 'status', 'user_id', 'datetime_modified', 'datetime_created')

    def setUp(self):
        super().setUp()
        self.approval, self.sha = self._ready_to_apply()
        self.original = list(Order.objects.order_by('pk').values_list(*self.FIELDS))
        self._apply(self.approval, self.sha)

    def _state(self):
        return list(Order.objects.order_by('pk').values_list(*self.FIELDS))

    def _refused(self, message, **kwargs):
        state = self._state()
        kwargs.setdefault('report', f'rb-{len(list(self.dir.iterdir()))}.csv')
        with self.assertRaisesMessage(CommandError, message):
            self._rollback(self.approval, self.sha, **kwargs)
        self.assertFalse((self.dir / kwargs['report']).exists())
        self.assertEqual(self._state(), state)

    def test_rollback_restores_exactly_the_original_values_and_is_idempotent(self):
        out = self._rollback(self.approval, self.sha)
        self.assertIn('R1A: 2 orders restored', out)
        self.assertEqual(self._state(), self.original)
        rows = self._rows('rollback.csv')
        self.assertEqual([r['status'] for r in rows], ['ROLLBACK_INTENDED', 'ROLLBACK_INTENDED', 'ROLLBACK_STARTED', 'ROLLBACK_COMMITTED'])
        execution_sha = hashlib.sha256((self.dir / 'execution.csv').read_bytes()).hexdigest()
        self.assertEqual({r['execution_report_sha256'] for r in rows}, {execution_sha})
        self.assertEqual(self._value(out, 'rollback_report_sha256'), hashlib.sha256((self.dir / 'rollback.csv').read_bytes()).hexdigest())

        with CaptureQueriesContext(connection) as ctx:
            again = self._rollback(self.approval, self.sha, report='rollback-2.csv')
        self.assertEqual([q['sql'] for q in ctx.captured_queries if q['sql'].lstrip().upper().startswith(WRITE_SQL)], [])
        self.assertIn('Nothing to roll back (RUN_COMMITTED)', again)
        self.assertEqual(self._rows('rollback-2.csv')[-1]['status'], 'ROLLBACK_NOOP_ALREADY_RESTORED')
        self._preview('after-rollback.csv', 'R1A')
        self.assertEqual({r['category'] for wp, r in self._by_wp('after-rollback.csv').items() if wp in (101, 115)}, {'PROPOSED'})

    def test_rollback_is_disabled_in_code(self):
        self._refused('Execution is disabled in this build', enabled=False)

    def test_rows_changed_after_the_correction_block_the_whole_rollback(self):
        cases = (
            ('DB_TOTAL_CHANGED=1', lambda: Order.objects.filter(wordpress_id=101).update(total_price=5)),
            ('DB_IS_PAID_CHANGED=1', lambda: Order.objects.filter(wordpress_id=115).update(is_paid=True)),
            ('DB_PAYMENT_PRESENT=1', lambda: Payment.objects.create(order=self.orders[101], gateway='sep', amount=1)),
            ('DB_ORDER_MISSING=1', lambda: Order.objects.filter(wordpress_id=115).delete()),
        )
        for message, change in cases:
            with self.subTest(case=message):
                change()
                self._refused(message)

    def test_mixed_state_is_refused(self):
        Order.objects.filter(wordpress_id=115).update(total_price=2000000)
        self._refused('refusing a mixed state')
        self.assertEqual(self._totals(101), {101: 196500})

    def test_change_during_the_rollback_transaction_rolls_everything_back(self):
        real = correction.Command._restore_one
        calls = []

        def edit_then_restore(using, target):
            calls.append(target)
            if len(calls) == 2:
                Order.objects.filter(pk=target['order_id']).update(total_price=target['proposed_after'] + 1)
            return real(using, target)

        with mock.patch.object(correction.Command, '_restore_one', staticmethod(edit_then_restore)):
            with self.assertRaisesMessage(CommandError, 'changed during the rollback'):
                self._rollback(self.approval, self.sha)
        self.assertEqual(self._totals(101, 115), {101: 196500, 115: 200000})
        self.assertEqual(self._rows('rollback.csv')[-1]['status'], 'ROLLBACK_ROLLED_BACK')

    def test_failure_during_the_batch_leaves_no_partial_rollback_and_a_retry_succeeds(self):
        real = correction.Command._restore_one
        calls = []

        def fail_second(using, target):
            calls.append(target)
            if len(calls) == 2:
                raise RuntimeError('simulated failure')
            return real(using, target)

        with mock.patch.object(correction.Command, '_restore_one', staticmethod(fail_second)):
            with self.assertRaisesMessage(CommandError, 'Rollback rolled back (RuntimeError)'):
                self._rollback(self.approval, self.sha)
        self.assertEqual(self._totals(101, 115), {101: 196500, 115: 200000})
        self._rollback(self.approval, self.sha, report='retry.csv')
        self.assertEqual(self._state(), self.original)

    def test_identity_mismatch_refuses_the_rollback(self):
        real = correction.database_identity(connection.alias)
        with mock.patch.object(correction, 'database_identity', return_value={**real, 'system_identifier': '1'}):
            self._refused('not the database recorded')

    def _tampered(self, transform):
        lines = (self.dir / 'execution.csv').read_text(encoding='utf-8').splitlines(keepends=True)
        body = ''.join(transform(lines)).encode('utf-8')
        name = f'tampered-{len(list(self.dir.iterdir()))}.csv'
        (self.dir / name).write_bytes(body)
        return name, hashlib.sha256(body).hexdigest()

    def test_tampered_incomplete_or_foreign_reports_are_rejected(self):
        pk101, pk102 = self.orders[101].pk, self.orders[102].pk
        other_sha = 'a' * 64
        cases = {
            'edited value': (lambda ls: [ls[0], ls[1].replace(',196500,', ',196501,')] + ls[2:], 'values differ from the before-state'),
            'duplicate row': (lambda ls: ls[:2] + [ls[1]] + ls[2:], 'duplicate order_id or wordpress_id'),
            'missing row': (lambda ls: [ls[0], ls[1]] + ls[3:], 'does not list the complete approved batch'),
            'no RUN_STARTED': (lambda ls: ls[:3], 'incomplete or malformed'),
            'rolled back run': (lambda ls: ls[:-1] + [ls[-1].replace('RUN_COMMITTED', 'RUN_ROLLED_BACK')], 'records a rolled-back run'),
            'unknown status': (lambda ls: ls[:-1] + [ls[-1].replace('RUN_COMMITTED', 'RUN_DONE')], 'incomplete or malformed'),
            'marker totals': (lambda ls: ls[:-1] + [ls[-1].replace(',3965000,', ',3965001,')], 'status totals do not match'),
            'foreign order': (lambda ls: [ls[0], ls[1].replace(f'INTENDED,{pk101},101,', f'INTENDED,{pk102},102,')] + ls[2:],
                              'is not part of the approved R1A batch'),
            'extra column': (lambda ls: [ls[0], ls[1].rstrip('\n') + ',x\n'] + ls[2:], 'expected 14 columns'),
            'header': (lambda ls: ['status,order_id\n'] + ls[1:], 'header does not match'),
            'other approval': (lambda ls: [ls[0]] + [l.replace(self.sha, other_sha) for l in ls[1:]], 'bound to a different approval'),
            'signed id': (lambda ls: [ls[0], ls[1].replace(f'INTENDED,{pk101},', f'INTENDED,+{pk101},')] + ls[2:], 'not a non-negative integer'),
            'no-op report': (lambda ls: [ls[0]] + [l.replace('INTENDED', 'ALREADY_APPLIED') for l in ls[1:3]] + ls[3:], 'incomplete or malformed'),
        }
        for name, (transform, message) in cases.items():
            with self.subTest(case=name):
                report, report_sha = self._tampered(transform)
                self._refused(message, execution=report, execution_sha=report_sha)
        self._refused('does not match --execution-report-sha256', execution_sha='b' * 64)
        self.assertEqual(self._totals(101, 115), {101: 196500, 115: 200000})

    def test_rollback_needs_the_authorised_approval_of_the_run(self):
        correction.AUTHORIZED_APPROVALS.clear()
        self._refused('not recorded in AUTHORIZED_APPROVALS')
