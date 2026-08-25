from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_('user'))
    is_paid = models.BooleanField(_('is_paid?'), default=False)

    first_name = models.CharField(_('first_name'), max_length=100)
    last_name = models.CharField(_('last_name'), max_length=100)
    phone_number = models.CharField(_('phone_number'), max_length=15)
    address = models.CharField(_('address'), max_length=700)
    order_notes = models.CharField(_("note"), max_length=700, blank=True)

    # فیلدهای جدید
    total_weight = models.PositiveIntegerField(_('total weight'), default=0, help_text=_('وزن کل سفارش (گرم)'))
    total_price = models.PositiveIntegerField(_('total price'), default=0, help_text=_('مبلغ کل سفارش (تومان)'))

    datetime_created = models.DateTimeField(_('Date Time of Creation'), auto_now_add=True)
    datetime_modified = models.DateTimeField(_('Date Time of Modified'), auto_now=True)

    def __str__(self):
        return f'Order {self.id}'

    def get_total_price(self):
        """محاسبه قیمت کل سفارش"""
        return sum(item.quantity * item.price for item in self.items.all())

    def get_total_weight(self):
        """محاسبه وزن کل سفارش"""
        return sum(item.get_weight() for item in self.items.all())


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='order_items', null=True, blank=True)
    package = models.ForeignKey('products.Package', on_delete=models.CASCADE, related_name='order_items', null=True, blank=True)
    quantity = models.PositiveBigIntegerField(default=1)
    price = models.PositiveIntegerField(verbose_name=_('Product Price'))

    def __str__(self):
        if self.product:
            return f'OrderItem {self.id}: {self.product.title} * {self.quantity} (price: {self.price})'
        elif self.package:
            return f'OrderItem {self.id}: {self.package.title} * {self.quantity} (price: {self.price})'
        return f'OrderItem {self.id}'

    def get_weight(self):
        """وزن این آیتم"""
        if self.product and self.product.weight:
            return self.product.weight * self.quantity
        if self.package:
            return self.package.get_total_weight() * self.quantity
        return 0

    def get_title(self):
        """عنوان آیتم"""
        if self.product:
            return self.product.title
        elif self.package:
            return self.package.title
        return 'Unknown'

class ReturnRequest(models.Model):
    """درخواست برگشت کالا"""
    
    class ReturnStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        RETURNED = 'RETURNED', _('Returned')
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests', verbose_name=_('order'))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='return_requests', verbose_name=_('user'))
    
    reason = models.TextField(_('reason'), help_text=_('Reason for return'))
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=ReturnStatus.choices,
        default=ReturnStatus.PENDING,
    )
    
    admin_note = models.TextField(_('admin note'), blank=True, help_text=_('Admin note'))
    
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    datetime_updated = models.DateTimeField(_('updated'), auto_now=True)
    
    class Meta:
        verbose_name = _('Return Request')
        verbose_name_plural = _('Return Requests')
        ordering = ['-datetime_created']
    
    def __str__(self):
        return f'Return #{self.id} - Order #{self.order.id}'
    
    def is_approved(self):
        return self.status == self.ReturnStatus.APPROVED
    
    def is_rejected(self):
        return self.status == self.ReturnStatus.REJECTED
    
    def is_returned(self):
        return self.status == self.ReturnStatus.RETURNED
    
    def can_request_return(self):
        """بررسی ۳ روز مهلت"""
        from django.utils import timezone
        days_since_order = (timezone.now() - self.order.datetime_created).days
        return days_since_order <= 3 and self.order.is_paid