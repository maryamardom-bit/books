from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from orders.factories import OrderFactory, OrderItemFactory
from orders.models import Order
from products.factories import DiscountCodeFactory, PackageFactory, ProductFactory
from products.models import TieredDiscount

from .gateways.sep import SepGateway
from .models import Payment

User = get_user_model()

SEP_POST = 'payment.gateways.sep.requests.post'


def _response(payload, status_code=200):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def _token_ok(token='test_token_123'):
    return _response({'status': 1, 'token': token})


def _verify_ok(payment, ref_num='REF123456', amount=None):
    return _response({
        'TransactionDetail': {
            'RRN': '14226761817',
            'RefNum': ref_num,
            'MaskedPan': '621986****8080',
            'TerminalNumber': 2015,
            'OrginalAmount': payment.amount * 10 if amount is None else amount,
            'AffectiveAmount': payment.amount * 10 if amount is None else amount,
            'StraceNo': '100408',
        },
        'ResultCode': 0,
        'ResultDescription': 'عملیات با موفقیت انجام شد',
        'Success': True,
    })


def _callback(payment, status='2', ref_num='REF123456'):
    return {
        'ResNum': payment.reference.hex,
        'RefNum': ref_num,
        'Status': status,
        'State': 'OK' if status == '2' else 'CanceledByUser',
        'TraceNo': '100408',
        'Rrn': '14226761817',
        'Amount': str(payment.amount * 10),
        'SecurePan': '621986****8080',
    }


@override_settings(SEP_TERMINAL_ID='2015', PAYMENT_AMOUNT_MULTIPLIER=10)
class PaymentProcessTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='paymentuser', password='testpass123', phone_number='09123456789')
        self.client.login(username='paymentuser', password='testpass123')
        self.product = ProductFactory(price=100000, stock=10)
        self.order = OrderFactory(user=self.user, total_price=200000, total_weight=1000, is_paid=False)
        session = self.client.session
        session['order_id'] = self.order.id
        session.save()

    @patch(SEP_POST)
    def test_redirects_to_gateway_with_rial_amount(self, mock_post):
        mock_post.return_value = _token_ok()

        response = self.client.get(reverse('payment:payment_process'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('sep.shaparak.ir', response.url)
        self.assertIn('test_token_123', response.url)
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        payload = mock_post.call_args.kwargs['json']
        self.assertEqual(payload['action'], 'token')
        self.assertEqual(payload['TerminalId'], '2015')
        self.assertEqual(payload['Amount'], 2000000)  # 200,000 Toman = 2,000,000 Rial
        self.assertEqual(payload['ResNum'], payment.reference.hex)
        self.assertTrue(payload['RedirectUrl'].endswith(reverse('payment:payment_verify')))

    @patch(SEP_POST)
    def test_gateway_rejection(self, mock_post):
        mock_post.return_value = _response({'status': -1, 'errorCode': 5, 'errorDesc': 'Invalid terminal'})

        response = self.client.get(reverse('payment:payment_process'))

        self.assertRedirects(response, reverse('cart:cart_detail'))
        self.assertEqual(Payment.objects.get(order=self.order).status, Payment.Status.FAILED)

    @patch(SEP_POST)
    def test_gateway_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()

        response = self.client.get(reverse('payment:payment_process'))

        self.assertRedirects(response, reverse('cart:cart_detail'))
        self.assertEqual(Payment.objects.get(order=self.order).status, Payment.Status.FAILED)

    def test_no_order(self):
        session = self.client.session
        session.pop('order_id', None)
        session.save()

        response = self.client.get(reverse('payment:payment_process'))

        self.assertRedirects(response, reverse('cart:cart_detail'))

    def test_already_paid(self):
        self.order.is_paid = True
        self.order.status = Order.Status.PAID
        self.order.save()

        response = self.client.get(reverse('payment:payment_process'))

        self.assertRedirects(response, reverse('page:home'))

    def test_cannot_pay_someone_elses_order(self):
        other = OrderFactory(is_paid=False)
        response = self.client.get(reverse('payment:payment_process'), {'order': other.id})
        self.assertEqual(response.status_code, 404)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('payment:payment_process'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_zero_total_completes_without_gateway(self):
        self.order.total_price = 0
        self.order.save()
        OrderItemFactory(order=self.order, product=self.product, quantity=1, price=0)

        with patch(SEP_POST) as mock_post:
            response = self.client.get(reverse('payment:payment_process'))
            mock_post.assert_not_called()

        self.assertRedirects(response, reverse('accounts:order_history'))
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)


@override_settings(SEP_TERMINAL_ID='2015', PAYMENT_AMOUNT_MULTIPLIER=10)
class PaymentCallbackTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='verifyuser', password='testpass123', phone_number='09123456789')
        self.product = ProductFactory(price=50000, stock=10)
        self.order = OrderFactory(user=self.user, total_price=100000, total_weight=500, is_paid=False)
        OrderItemFactory(order=self.order, product=self.product, quantity=2, price=50000)
        self.payment = Payment.objects.create(
            order=self.order, gateway='sep', amount=100000, status=Payment.Status.PENDING,
        )
        # The bank posts cross-site: no session cookie, no logged-in user.
        self.bank = Client()

    def _post(self, data):
        return self.bank.post(reverse('payment:payment_verify'), data)

    @patch(SEP_POST)
    def test_success_marks_paid_and_decreases_stock(self, mock_post):
        mock_post.return_value = _verify_ok(self.payment)

        response = self._post(_callback(self.payment))

        self.assertRedirects(response, reverse('page:home'))
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(self.order.is_paid)
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertEqual(self.payment.transaction_id, 'REF123456')
        self.assertEqual(self.product.stock, 8)
        verify_payload = mock_post.call_args.kwargs['json']
        self.assertEqual(verify_payload, {'RefNum': 'REF123456', 'TerminalNumber': 2015})

    @patch(SEP_POST)
    def test_callback_replay_is_idempotent(self, mock_post):
        mock_post.return_value = _verify_ok(self.payment)

        self._post(_callback(self.payment))
        response = self._post(_callback(self.payment))

        self.assertRedirects(response, reverse('page:home'))
        self.assertEqual(mock_post.call_count, 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    @patch(SEP_POST)
    def test_advances_tier_and_counts_discount_code(self, mock_post):
        code = DiscountCodeFactory(code='SPRING', used_count=0, max_uses=5)
        self.order.discount_code = 'SPRING'
        self.order.save()
        tiered = TieredDiscount.objects.create(user=self.user, current_tier=0)
        mock_post.return_value = _verify_ok(self.payment)

        self._post(_callback(self.payment))

        tiered.refresh_from_db()
        code.refresh_from_db()
        self.assertEqual(tiered.current_tier, 1)
        self.assertEqual(code.used_count, 1)

    @patch(SEP_POST)
    def test_cancelled_at_gateway(self, mock_post):
        response = self._post(_callback(self.payment, status='1'))

        self.assertRedirects(response, reverse('cart:cart_detail'))
        mock_post.assert_not_called()
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertFalse(self.order.is_paid)
        self.assertEqual(self.order.status, Order.Status.PAYMENT_FAILED)
        self.assertEqual(self.payment.status, Payment.Status.CANCELLED)

    @patch(SEP_POST)
    def test_verify_rejected(self, mock_post):
        mock_post.return_value = _response({'ResultCode': -2, 'ResultDescription': 'تراکنش یافت نشد', 'Success': False})

        self._post(_callback(self.payment))

        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertFalse(self.order.is_paid)
        self.assertEqual(self.product.stock, 10)

    @patch(SEP_POST)
    def test_amount_mismatch_is_rejected_and_reversed(self, mock_post):
        mock_post.side_effect = [
            _verify_ok(self.payment, amount=1000),
            _response({'ResultCode': 0, 'Success': True}),
        ]

        self._post(_callback(self.payment))

        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertFalse(self.order.is_paid)
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_post.call_args_list[1].args[0], SepGateway.REVERSE_URL)

    @patch(SEP_POST)
    def test_verify_timeout_keeps_payment_pending_for_retry(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()

        response = self._post(_callback(self.payment))

        self.assertRedirects(response, reverse('cart:cart_detail'))
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)
        self.assertFalse(self.order.is_paid)

        mock_post.side_effect = None
        mock_post.return_value = _verify_ok(self.payment)
        self._post(_callback(self.payment))
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)

    @patch(SEP_POST)
    def test_out_of_stock_is_not_verified(self, mock_post):
        self.product.stock = 1
        self.product.save()

        self._post(_callback(self.payment))

        mock_post.assert_not_called()
        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertFalse(self.order.is_paid)

    @patch(SEP_POST)
    def test_last_copy_sold_once(self, mock_post):
        """Two orders for the last copy: only the first verified payment wins, stock never < 0."""
        self.product.stock = 2
        self.product.save()
        other_order = OrderFactory(total_price=100000, is_paid=False)
        OrderItemFactory(order=other_order, product=self.product, quantity=2, price=50000)
        other_payment = Payment.objects.create(
            order=other_order, gateway='sep', amount=100000, status=Payment.Status.PENDING,
        )
        mock_post.return_value = _verify_ok(self.payment)

        self._post(_callback(self.payment))
        mock_post.return_value = _verify_ok(other_payment, ref_num='REF999')
        self._post(_callback(other_payment, ref_num='REF999'))

        self.product.refresh_from_db()
        other_order.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertFalse(other_order.is_paid)
        self.assertEqual(mock_post.call_count, 1)

    @patch(SEP_POST)
    def test_duplicate_transaction_id_rejected(self, mock_post):
        mock_post.return_value = _verify_ok(self.payment)
        self._post(_callback(self.payment))

        other_order = OrderFactory(total_price=100000, is_paid=False)
        other_payment = Payment.objects.create(
            order=other_order, gateway='sep', amount=100000, status=Payment.Status.PENDING,
        )
        self._post(_callback(other_payment, ref_num='REF123456'))

        other_order.refresh_from_db()
        other_payment.refresh_from_db()
        self.assertFalse(other_order.is_paid)
        self.assertEqual(other_payment.failure_reason, 'DUPLICATE_TRANSACTION')

    @patch(SEP_POST)
    def test_package_stock_decrease(self, mock_post):
        book = ProductFactory(price=80000, weight=300, stock=10)
        package = PackageFactory(products=[book], stock=5)
        order = OrderFactory(user=self.user, total_price=package.price * 3, is_paid=False)
        OrderItemFactory(order=order, product=None, package=package, quantity=3, price=package.price)
        payment = Payment.objects.create(order=order, gateway='sep', amount=order.total_price, status=Payment.Status.PENDING)
        mock_post.return_value = _verify_ok(payment, ref_num='PKG1')

        self._post(_callback(payment, ref_num='PKG1'))

        package.refresh_from_db()
        self.assertEqual(package.stock, 2)

    def test_unknown_reference(self):
        response = self._post({'ResNum': 'not-a-uuid', 'RefNum': 'X', 'Status': '2'})
        self.assertRedirects(response, reverse('cart:cart_detail'))

    def test_get_callback_without_params(self):
        response = self.bank.get(reverse('payment:payment_verify'))
        self.assertRedirects(response, reverse('cart:cart_detail'))


class PaymentURLTest(TestCase):
    def test_urls(self):
        self.assertEqual(reverse('payment:payment_process'), '/payment/process/')
        self.assertEqual(reverse('payment:payment_verify'), '/payment/verify/')


class PaymentCSRFExemptTest(TestCase):
    def test_callback_is_csrf_exempt(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse('payment:payment_verify'), {'ResNum': '', 'Status': '2'})
        self.assertNotEqual(response.status_code, 403)
