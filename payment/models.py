import uuid

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Payment(models.Model):
    """
    One attempt to pay an order through a gateway.
    An order may have several (retries); at most one can be PAID.

    TODO(Phase 2 - Payment): Refund / partial refund records and a gateway fee column
    for financial reports.
    """

    class Status(models.TextChoices):
        INITIATED = 'INITIATED', _('Initiated')
        PENDING = 'PENDING', _('Pending at gateway')
        PAID = 'PAID', _('Paid')
        FAILED = 'FAILED', _('Failed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name=_('order'),
    )
    gateway = models.CharField(_('gateway'), max_length=30)
    # Sent to the gateway as our invoice number; the callback is matched by this, not by session.
    reference = models.UUIDField(_('reference'), default=uuid.uuid4, unique=True, editable=False)
    # Same unit as Order.total_price (Toman). Gateways convert to their own unit.
    amount = models.BigIntegerField(_('amount'))
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
        db_index=True,
    )
    token = models.CharField(_('token'), max_length=255, blank=True)
    transaction_id = models.CharField(_('transaction id'), max_length=100, null=True, blank=True)
    rrn = models.CharField(_('RRN'), max_length=50, blank=True)
    trace_no = models.CharField(_('trace number'), max_length=50, blank=True)
    card_mask = models.CharField(_('card'), max_length=32, blank=True)
    failure_reason = models.CharField(_('failure reason'), max_length=255, blank=True)
    callback_payload = models.JSONField(_('callback payload'), default=dict, blank=True)
    verify_payload = models.JSONField(_('verify payload'), default=dict, blank=True)

    created_at = models.DateTimeField(_('created'), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_('updated'), auto_now=True)
    paid_at = models.DateTimeField(_('paid at'), null=True, blank=True)

    class Meta:
        verbose_name = _('payment')
        verbose_name_plural = _('payments')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['gateway', 'transaction_id'],
                condition=Q(transaction_id__isnull=False),
                name='payment_unique_gateway_transaction',
            ),
            models.UniqueConstraint(
                fields=['order'],
                condition=Q(status='PAID'),
                name='payment_one_paid_per_order',
            ),
        ]

    def __str__(self):
        return f'Payment {self.reference} ({self.status})'
