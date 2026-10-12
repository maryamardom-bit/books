from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class InvalidOrderTransition(Exception):
    pass


class Order(models.Model):

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        PENDING_PAYMENT = 'PENDING_PAYMENT', _('Pending payment')
        PAYMENT_FAILED = 'PAYMENT_FAILED', _('Payment failed')
        PAID = 'PAID', _('Paid')
        PROCESSING = 'PROCESSING', _('Processing')
        PACKED = 'PACKED', _('Packed')
        SHIPPED = 'SHIPPED', _('Shipped')
        DELIVERED = 'DELIVERED', _('Delivered')
        CANCELLED = 'CANCELLED', _('Cancelled')
        RETURN_REQUESTED = 'RETURN_REQUESTED', _('Return requested')
        RETURNED = 'RETURNED', _('Returned')
        REFUNDED = 'REFUNDED', _('Refunded')

    TRANSITIONS = {
        Status.DRAFT: {Status.PENDING_PAYMENT, Status.CANCELLED},
        Status.PENDING_PAYMENT: {Status.PAID, Status.PAYMENT_FAILED, Status.CANCELLED},
        Status.PAYMENT_FAILED: {Status.PENDING_PAYMENT, Status.PAID, Status.CANCELLED},
        Status.PAID: {Status.PROCESSING, Status.CANCELLED, Status.RETURN_REQUESTED, Status.REFUNDED},
        Status.PROCESSING: {Status.PACKED, Status.CANCELLED},
        Status.PACKED: {Status.SHIPPED},
        Status.SHIPPED: {Status.DELIVERED, Status.RETURN_REQUESTED},
        Status.DELIVERED: {Status.RETURN_REQUESTED},
        Status.RETURN_REQUESTED: {Status.RETURNED, Status.PAID, Status.DELIVERED},
        Status.RETURNED: {Status.REFUNDED},
        Status.CANCELLED: set(),
        Status.REFUNDED: set(),
    }
    PAYABLE_STATUSES = {Status.PENDING_PAYMENT, Status.PAYMENT_FAILED}
    # Imported orders keep their historical status; they can never re-enter the payment flow.
    PAYMENT_STATUSES = PAYABLE_STATUSES | {Status.PAID}

    # Orders are financial records: users with orders cannot be hard-deleted.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name=_('user'))
    wordpress_id = models.PositiveIntegerField(
        _('wordpress id'),
        null=True,
        blank=True,
        unique=True,
        db_index=True,
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
        db_index=True,
    )
    # Kept for templates and reports: True once a payment has been captured, never reset.
    is_paid = models.BooleanField(_('is_paid?'), default=False)

    first_name = models.CharField(_('first name'), max_length=100)
    last_name = models.CharField(_('last name'), max_length=100)
    phone_number = models.CharField(_('phone number'), max_length=15)
    # TODO(Phase 2 - Shipping): replace free-text address with an Address snapshot
    # (province, city, postal code) so ShippingZone/ShippingRate can be computed.
    address = models.CharField(_('address'), max_length=700)
    order_notes = models.CharField(_('note'), max_length=700, blank=True)

    total_weight = models.PositiveIntegerField(_('total weight'), default=0)
    # Amount the customer pays, in Toman, after discounts.
    # TODO(Phase 2): store subtotal, discount_total, shipping_total and tax_total separately.
    total_price = models.BigIntegerField(_('total price'), default=0)
    # Usage is counted when payment succeeds; stored here because the bank callback has no session.
    discount_code = models.CharField(_('discount code'), max_length=50, blank=True)

    payment_method = models.CharField(
        _('payment method'),
        max_length=20,
        default='online',
        choices=[
            ('online', _('Online')),
            ('installment', _('Installment')),
        ],
    )
    
    installment_plan_id = models.CharField(
        _('installment plan'),
        max_length=20,
        blank=True,
    )

    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    datetime_modified = models.DateTimeField(_('modified'), auto_now=True)

    def __str__(self):
        return f'Order {self.id}'

    def get_total_price(self):
        return sum(item.quantity * item.price for item in self.items.all())

    def get_total_weight(self):
        return sum(item.get_weight() for item in self.items.all())

    @property
    def is_imported(self):
        # wordpress_id is set only by the WooCommerce importer, never by checkout.
        return self.wordpress_id is not None

    def is_payable(self):
        return not self.is_imported and not self.is_paid and self.status in self.PAYABLE_STATUSES

    def can_transition_to(self, new_status):
        if self.is_imported and new_status in self.PAYMENT_STATUSES:
            return False
        return new_status in self.TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status, save=True):
        if new_status == self.status:
            return
        if not self.can_transition_to(new_status):
            raise InvalidOrderTransition(f'{self.status} -> {new_status}')
        self.status = new_status
        if new_status == self.Status.PAID:
            self.is_paid = True
        if save:
            self.save(update_fields=['status', 'is_paid', 'datetime_modified'])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    # PROTECT: a book or package that was ever ordered must be archived (active=False), not deleted.
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='order_items', null=True, blank=True)
    package = models.ForeignKey('products.Package', on_delete=models.PROTECT, related_name='order_items', null=True, blank=True)
    # Snapshot at purchase time; later catalog edits must not rewrite order history.
    title = models.CharField(_('title'), max_length=255, blank=True, default='')
    quantity = models.PositiveBigIntegerField(default=1)
    price = models.PositiveIntegerField(verbose_name=_('Product Price'))

    def __str__(self):
        return f'OrderItem {self.id}: {self.get_title()}'

    def save(self, *args, **kwargs):
        if not self.title:
            item = self.product or self.package
            if item is not None:
                self.title = item.title[:255]
        super().save(*args, **kwargs)

    def get_weight(self):
        if self.product and self.product.weight:
            return self.product.weight * self.quantity
        if self.package:
            return self.package.get_total_weight() * self.quantity
        return 0

    def get_title(self):
        if self.title:
            return self.title
        if self.product:
            return self.product.title
        elif self.package:
            return self.package.title
        return 'Unknown'


class ReturnRequest(models.Model):
    """Return request"""
    # TODO(Phase 2 - Returns): drive Order.status (RETURN_REQUESTED/RETURNED/REFUNDED), support
    # per-line partial returns, inspection (restock vs damaged) and a Refund record.
    
    class ReturnStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        RETURNED = 'RETURNED', _('Returned')
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests', verbose_name=_('order'))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='return_requests', verbose_name=_('user'))
    
    reason = models.TextField(_('reason'))
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=ReturnStatus.choices,
        default=ReturnStatus.PENDING,
    )
    
    admin_note = models.TextField(_('admin note'), blank=True)
    
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    datetime_updated = models.DateTimeField(_('updated'), auto_now=True)
    
    class Meta:
        verbose_name = _('Return Request')
        verbose_name_plural = _('Return Requests')
        ordering = ['-datetime_created']
    
    def __str__(self):
        return f'Return #{self.id} - Order #{self.order.id}'
    
    def can_request_return(self):
        from django.utils import timezone
        days_since_order = (timezone.now() - self.order.datetime_created).days
        return days_since_order <= 3 and self.order.is_paid
