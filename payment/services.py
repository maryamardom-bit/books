"""
Payment use-cases. Views stay thin; every state change happens here inside a transaction.

Rules enforced:
- Only server-side verify() can mark a payment PAID (browser callback is untrusted).
- Callback replay is idempotent: a PAID payment is never verified or fulfilled twice.
- One gateway transaction id can pay one payment; one order can have one PAID payment.
- Stock rows are locked and checked before verify; if stock ran out the transaction is left
  unverified so the gateway auto-refunds it, and stock can never go negative.
"""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from orders.models import Order
from products.models import DiscountCode, Package, Product, TieredDiscount
from services.sms import SMSService

from .gateways import GatewayError, PaymentRejected, get_gateway
from .models import Payment

logger = logging.getLogger(__name__)

MESSAGES = {
    'PAID': _('Payment successful'),
    'ALREADY_PAID': _('Payment successful'),
    'PAYMENT_NOT_FOUND': _('Payment not found.'),
    'PAYMENT_NOT_PENDING': _('This payment is no longer pending.'),
    'PAYMENT_CANCELLED': _('Payment failed or cancelled.'),
    'ORDER_ALREADY_PAID': _('This order has already been paid.'),
    'ORDER_NOT_PAYABLE': _('This order can no longer be paid.'),
    'DUPLICATE_TRANSACTION': _('This transaction has already been used.'),
    'BOOK_OUT_OF_STOCK': _('Some items are no longer in stock. Your payment will be refunded by the bank.'),
    'PAYMENT_VERIFICATION_FAILED': _('Payment verification failed.'),
    'PAYMENT_AMOUNT_MISMATCH': _('Payment amount does not match the order.'),
    'GATEWAY_UNAVAILABLE': _('Error connecting to payment gateway.'),
    'GATEWAY_REJECTED': _('Payment error'),
}


class PaymentError(Exception):
    def __init__(self, code, detail=''):
        self.code = code
        self.detail = detail
        super().__init__(code)

    @property
    def message(self):
        base = str(MESSAGES.get(self.code, self.code))
        return f'{base}: {self.detail}' if self.detail else base


@dataclass
class CallbackOutcome:
    success: bool
    code: str
    payment: Payment = None

    @property
    def message(self):
        return str(MESSAGES.get(self.code, self.code))


def start_payment(order, callback_url):
    """
    Create a Payment and ask the gateway for a token.
    Returns the GatewayRedirect, or None when the order total is zero and was completed directly.
    """
    gateway = get_gateway()
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.is_paid:
            raise PaymentError('ORDER_ALREADY_PAID')
        if order.status not in (Order.Status.PENDING_PAYMENT, Order.Status.PAYMENT_FAILED):
            raise PaymentError('ORDER_NOT_PAYABLE')
        if order.status == Order.Status.PAYMENT_FAILED:
            order.transition_to(Order.Status.PENDING_PAYMENT)
        payment = Payment.objects.create(order=order, gateway=gateway.name, amount=order.total_price)

        if payment.amount <= 0:
            if not _lock_and_check_stock(order):
                _fail(payment, order, 'OUT_OF_STOCK')
                raise PaymentError('BOOK_OUT_OF_STOCK')
            _complete(payment, order)
            return None

    try:
        redirect = gateway.request_payment(payment, callback_url)
    except GatewayError:
        _fail(payment, None, 'GATEWAY_UNAVAILABLE')
        raise PaymentError('GATEWAY_UNAVAILABLE')
    except PaymentRejected as exc:
        _fail(payment, None, f'GATEWAY_REJECTED: {exc}')
        raise PaymentError('GATEWAY_REJECTED', str(exc))

    payment.token = redirect.token[:255]
    payment.status = Payment.Status.PENDING
    payment.save(update_fields=['token', 'status', 'updated_at'])
    return redirect


def handle_callback(data):
    """Process a gateway callback (browser redirect or webhook). Safe to call repeatedly."""
    gateway = get_gateway()
    callback = gateway.parse_callback(data)
    try:
        reference = uuid.UUID(callback.reference)
    except (ValueError, AttributeError):
        return CallbackOutcome(False, 'PAYMENT_NOT_FOUND')

    reverse_after_commit = None
    try:
        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .filter(reference=reference, gateway=gateway.name)
                .first()
            )
            if payment is None:
                return CallbackOutcome(False, 'PAYMENT_NOT_FOUND')
            if payment.status == Payment.Status.PAID:
                return CallbackOutcome(True, 'ALREADY_PAID', payment)
            if payment.status != Payment.Status.PENDING:
                return CallbackOutcome(False, 'PAYMENT_NOT_PENDING', payment)

            order = Order.objects.select_for_update().get(pk=payment.order_id)
            payment.callback_payload = callback.raw

            if not callback.success:
                _fail(payment, order, 'CANCELLED_AT_GATEWAY', status=Payment.Status.CANCELLED)
                return CallbackOutcome(False, 'PAYMENT_CANCELLED', payment)

            # Both cases are left unverified on purpose: the gateway refunds unverified transactions.
            if order.is_paid:
                _fail(payment, None, 'ORDER_ALREADY_PAID')
                return CallbackOutcome(False, 'ORDER_ALREADY_PAID', payment)
            if order.status not in (Order.Status.PENDING_PAYMENT, Order.Status.PAYMENT_FAILED):
                _fail(payment, None, f'ORDER_NOT_PAYABLE: {order.status}')
                return CallbackOutcome(False, 'ORDER_NOT_PAYABLE', payment)

            duplicate = (
                Payment.objects.filter(gateway=gateway.name, transaction_id=callback.transaction_id)
                .exclude(pk=payment.pk)
                .exists()
            )
            if callback.transaction_id and duplicate:
                _fail(payment, order, 'DUPLICATE_TRANSACTION')
                return CallbackOutcome(False, 'DUPLICATE_TRANSACTION', payment)

            if not _lock_and_check_stock(order):
                _fail(payment, order, 'OUT_OF_STOCK')
                return CallbackOutcome(False, 'BOOK_OUT_OF_STOCK', payment)

            result = gateway.verify(payment, callback)
            payment.verify_payload = result.raw
            if not result.success:
                _fail(payment, order, f'VERIFY_FAILED: {result.message}')
                return CallbackOutcome(False, 'PAYMENT_VERIFICATION_FAILED', payment)

            payment.transaction_id = result.transaction_id or callback.transaction_id
            payment.rrn = result.rrn[:50]
            payment.trace_no = result.trace_no[:50]
            payment.card_mask = result.card_mask

            expected = gateway.to_gateway_amount(payment.amount)
            if result.amount != expected or payment.transaction_id != callback.transaction_id:
                _fail(payment, order, f'AMOUNT_MISMATCH: expected {expected}, got {result.amount}')
                reverse_after_commit = payment
                return CallbackOutcome(False, 'PAYMENT_AMOUNT_MISMATCH', payment)

            _complete(payment, order)
            return CallbackOutcome(True, 'PAID', payment)
    except GatewayError:
        # Verify outcome unknown: keep PENDING so a replayed callback can retry verification.
        return CallbackOutcome(False, 'GATEWAY_UNAVAILABLE')
    finally:
        if reverse_after_commit is not None and not gateway.reverse(reverse_after_commit):
            logger.error('Reverse failed for payment %s; refund manually.', reverse_after_commit.pk)


def _fail(payment, order, reason, status=Payment.Status.FAILED):
    payment.status = status
    payment.failure_reason = reason[:255]
    payment.save()
    if order is not None and order.can_transition_to(Order.Status.PAYMENT_FAILED):
        order.transition_to(Order.Status.PAYMENT_FAILED)


def _order_quantities(order):
    products = defaultdict(int)
    packages = defaultdict(int)
    for item in order.items.all():
        if item.product_id:
            products[item.product_id] += item.quantity
        elif item.package_id:
            packages[item.package_id] += item.quantity
    return products, packages


def _lock_and_check_stock(order):
    """Row-lock every product/package of the order (in pk order, to avoid deadlocks) and check stock."""
    products, packages = _order_quantities(order)
    locked_products = list(Product.objects.select_for_update().filter(pk__in=products).order_by('pk'))
    locked_packages = list(Package.objects.select_for_update().filter(pk__in=packages).order_by('pk'))
    if len(locked_products) != len(products) or len(locked_packages) != len(packages):
        return False
    for product in locked_products:
        if product.stock - product.reserved_stock < products[product.pk]:
            return False
    for package in locked_packages:
        if package.stock < packages[package.pk]:
            return False
    return True


def _complete(payment, order):
    """Caller must hold the row locks taken by _lock_and_check_stock()."""
    payment.status = Payment.Status.PAID
    payment.paid_at = timezone.now()
    payment.failure_reason = ''
    payment.save()

    # TODO(Phase 1 - Inventory): write a SALE StockTransaction per line instead of mutating stock.
    products, packages = _order_quantities(order)
    for product_id, quantity in products.items():
        Product.objects.filter(pk=product_id).update(stock=F('stock') - quantity)
    for package_id, quantity in packages.items():
        Package.objects.filter(pk=package_id).update(stock=F('stock') - quantity)

    order.transition_to(Order.Status.PAID)

    if order.discount_code:
        DiscountCode.objects.filter(code=order.discount_code).update(used_count=F('used_count') + 1)

    tiered, _created = TieredDiscount.objects.get_or_create(user_id=order.user_id)
    tiered.advance_tier()

    user = order.user
    if user.phone_number:
        transaction.on_commit(lambda: SMSService.send_payment_confirmation_sms(user, order))
