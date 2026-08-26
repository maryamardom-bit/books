from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('user'))
    is_paid = models.BooleanField(_('is_paid?'), default=False)

    first_name = models.CharField(_('first name'), max_length=100)
    last_name = models.CharField(_('last name'), max_length=100)
    phone_number = models.CharField(_('phone number'), max_length=15)
    address = models.CharField(_('address'), max_length=700)
    order_notes = models.CharField(_('note'), max_length=700, blank=True)

    total_weight = models.PositiveIntegerField(_('total weight'), default=0)
    total_price = models.PositiveIntegerField(_('total price'), default=0)

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


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='order_items', null=True, blank=True)
    package = models.ForeignKey('products.Package', on_delete=models.CASCADE, related_name='order_items', null=True, blank=True)
    quantity = models.PositiveBigIntegerField(default=1)
    price = models.PositiveIntegerField(verbose_name=_('Product Price'))

    def __str__(self):
        return f'OrderItem {self.id}: {self.get_title()}'

    def get_weight(self):
        if self.product and self.product.weight:
            return self.product.weight * self.quantity
        if self.package:
            return self.package.get_total_weight() * self.quantity
        return 0

    def get_title(self):
        if self.product:
            return self.product.title
        elif self.package:
            return self.package.title
        return 'Unknown'


class ReturnRequest(models.Model):
    """Return request"""
    
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