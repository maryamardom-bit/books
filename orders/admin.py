from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db import models as django_models, transaction
from django.db.models import F
from jalali_date.admin import ModelAdminJalaliMixin
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime
import jdatetime

from .models import InvalidOrderTransition, Order, OrderItem, ReturnRequest
from services.sms import SMSService


class OrderItemInLine(admin.TabularInline):
    model = OrderItem
    fields = ['product', 'package', 'title', 'quantity', 'price', 'get_weight_display']
    # Order lines are a purchase snapshot; editing them would desync totals and payments.
    readonly_fields = ['product', 'package', 'title', 'quantity', 'price', 'get_weight_display']
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def get_weight_display(self, obj):
        weight = obj.get_weight()
        if weight > 0:
            return f'{weight} {_("g")}'
        return '-'
    get_weight_display.short_description = _('Weight')


@admin.register(Order)
class OrderAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = [
        'id', 'user', 'first_name', 'last_name', 'phone_number',
        'total_price_display', 'total_weight_display', 'status', 'is_paid',
        'datetime_created_jalali',
    ]
    list_filter = ['status', 'is_paid', 'datetime_created']
    search_fields = ['user__username', 'first_name', 'last_name', 'phone_number']
    # status / is_paid change only through the state machine (payment service or actions below).
    readonly_fields = [
        'status', 'is_paid', 'discount_code',
        'datetime_created', 'datetime_modified', 'total_price', 'total_weight',
    ]
    list_per_page = 20
    actions = [
        'mark_paid_offline', 'mark_processing', 'mark_packed',
        'mark_shipped', 'mark_delivered', 'mark_cancelled',
    ]

    fieldsets = (
        (_('User Info'), {'fields': ('user', 'first_name', 'last_name', 'phone_number')}),
        (_('Address'), {'fields': ('address', 'order_notes')}),
        (_('Payment'), {'fields': ('status', 'is_paid', 'total_price', 'discount_code', 'total_weight')}),
        (_('Dates'), {'fields': ('datetime_created', 'datetime_modified'), 'classes': ('collapse',)}),
    )

    inlines = [OrderItemInLine]

    # TODO(Phase 1 - Audit): write an AuditLog row (user, action, old/new value, IP) for every action.
    def _transition(self, request, queryset, new_status):
        moved, skipped = 0, 0
        for order in queryset:
            with transaction.atomic():
                locked = Order.objects.select_for_update().get(pk=order.pk)
                try:
                    locked.transition_to(new_status)
                    moved += 1
                except InvalidOrderTransition:
                    skipped += 1
        self.message_user(request, _('%(moved)s orders updated, %(skipped)s skipped (invalid transition).') % {
            'moved': moved, 'skipped': skipped,
        }, messages.SUCCESS if not skipped else messages.WARNING)

    @admin.action(description=_('Mark as paid (offline payment, no stock change)'))
    def mark_paid_offline(self, request, queryset):
        # TODO(Phase 1 - Inventory): offline payments must also post SALE stock transactions.
        self._transition(request, queryset, Order.Status.PAID)

    @admin.action(description=_('Mark as processing'))
    def mark_processing(self, request, queryset):
        self._transition(request, queryset, Order.Status.PROCESSING)

    @admin.action(description=_('Mark as packed'))
    def mark_packed(self, request, queryset):
        self._transition(request, queryset, Order.Status.PACKED)

    @admin.action(description=_('Mark as shipped'))
    def mark_shipped(self, request, queryset):
        # TODO(Phase 2 - Shipping): create a Shipment with carrier and tracking number.
        self._transition(request, queryset, Order.Status.SHIPPED)

    @admin.action(description=_('Mark as delivered'))
    def mark_delivered(self, request, queryset):
        self._transition(request, queryset, Order.Status.DELIVERED)

    @admin.action(description=_('Cancel orders'))
    def mark_cancelled(self, request, queryset):
        # TODO(Phase 2): cancelling a PAID order must restock and create a Refund.
        self._transition(request, queryset, Order.Status.CANCELLED)

    formfield_overrides = {
        django_models.DateField: {'widget': AdminJalaliDateWidget},
        django_models.DateTimeField: {'widget': AdminSplitJalaliDateTime},
    }

    def total_price_display(self, obj):
        return f'{obj.total_price:,} {_("Toman")}'
    total_price_display.short_description = _('Total Price')

    def total_weight_display(self, obj):
        if obj.total_weight > 0:
            return f'{obj.total_weight:,} {_("g")}'
        return '-'
    total_weight_display.short_description = _('Total Weight')

    def datetime_created_jalali(self, obj):
        """Display Jalali datetime"""
        if obj.datetime_created:
            jalali_date = jdatetime.datetime.fromgregorian(datetime=obj.datetime_created)
            return jalali_date.strftime('%Y/%m/%d %H:%M')
        return '-'
    datetime_created_jalali.short_description = _('Created')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'get_item_title', 'quantity', 'price', 'get_weight_display']
    list_filter = ['order__is_paid']
    search_fields = ['order__id', 'product__title', 'package__title']
    list_per_page = 20

    def get_item_title(self, obj):
        return obj.get_title()
    get_item_title.short_description = _('Title')

    def get_weight_display(self, obj):
        weight = obj.get_weight()
        if weight > 0:
            return f'{weight} {_("g")}'
        return '-'
    get_weight_display.short_description = _('Weight')


@admin.register(ReturnRequest)
class ReturnRequestAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = [
        'id',
        'order',
        'user',
        'status_display',
        'datetime_created_jalali',
        'datetime_updated_jalali',
    ]
    list_filter = ['status', 'datetime_created']
    search_fields = ['order__id', 'user__username', 'reason']
    readonly_fields = ['datetime_created', 'datetime_updated']
    list_per_page = 20

    fieldsets = (
        (_('Info'), {'fields': ('order', 'user', 'status', 'reason', 'admin_note')}),
        (_('Dates'), {'fields': ('datetime_created', 'datetime_updated'), 'classes': ('collapse',)}),
    )

    actions = ['approve_returns', 'reject_returns', 'mark_as_returned']

    def status_display(self, obj):
        """Display status with proper text color"""
        status_styles = {
            'PENDING': {
                'bg': '#fff3cd',
                'text': '#856404',
                'label': _('Pending'),
            },
            'APPROVED': {
                'bg': '#d4edda',
                'text': '#155724',
                'label': _('Approved'),
            },
            'REJECTED': {
                'bg': '#f8d7da',
                'text': '#721c24',
                'label': _('Rejected'),
            },
            'RETURNED': {
                'bg': '#cce5ff',
                'text': '#004085',
                'label': _('Returned'),
            },
        }
        
        style = status_styles.get(obj.status, {
            'bg': '#f5f0eb',
            'text': '#333',
            'label': obj.status,
        })
        
        return format_html(
            '<span style="background: {}; color: {}; padding: 4px 15px; border-radius: 15px; font-size: 12px; font-weight: 700;">{}</span>',
            style['bg'],
            style['text'],
            style['label'],
        )
    status_display.short_description = _('Status')

    def datetime_created_jalali(self, obj):
        """Display Jalali created datetime"""
        if obj.datetime_created:
            jalali_date = jdatetime.datetime.fromgregorian(datetime=obj.datetime_created)
            return jalali_date.strftime('%Y/%m/%d %H:%M')
        return '-'
    datetime_created_jalali.short_description = _('Created')

    def datetime_updated_jalali(self, obj):
        """Display Jalali updated datetime"""
        if obj.datetime_updated:
            jalali_date = jdatetime.datetime.fromgregorian(datetime=obj.datetime_updated)
            return jalali_date.strftime('%Y/%m/%d %H:%M')
        return '-'
    datetime_updated_jalali.short_description = _('Updated')

    def approve_returns(self, request, queryset):
        """Approve return requests and restock items"""
        # TODO(Phase 2 - Returns): restock only after physical receipt + inspection
        # (restockable vs damaged) and record a Refund instead of a raw wallet credit.
        from products.models import Package, Product

        User = get_user_model()
        count = 0
        for return_request in queryset:
            with transaction.atomic():
                locked = ReturnRequest.objects.select_for_update().get(pk=return_request.pk)
                if locked.status != ReturnRequest.ReturnStatus.PENDING:
                    continue
                locked.status = ReturnRequest.ReturnStatus.APPROVED
                locked.save(update_fields=['status', 'datetime_updated'])

                for item in locked.order.items.all():
                    if item.product_id:
                        Product.objects.filter(pk=item.product_id).update(stock=F('stock') + item.quantity)
                    elif item.package_id:
                        Package.objects.filter(pk=item.package_id).update(stock=F('stock') + item.quantity)

                User.objects.filter(pk=locked.user_id).update(
                    wallet_balance=F('wallet_balance') + locked.order.total_price
                )

                user = locked.user
                order = locked.order
                if user.phone_number:
                    transaction.on_commit(
                        lambda u=user, o=order, r=locked: SMSService.send_return_confirmation_sms(u, o, r)
                    )

            count += 1

        self.message_user(request, f'{count} {_("return requests approved.")}')
    approve_returns.short_description = _('Approve selected returns')

    def reject_returns(self, request, queryset):
        """Reject return requests"""
        updated = queryset.filter(status=ReturnRequest.ReturnStatus.PENDING).update(
            status=ReturnRequest.ReturnStatus.REJECTED
        )
        self.message_user(request, f'{updated} {_("return requests rejected.")}')
    reject_returns.short_description = _('Reject selected returns')

    def mark_as_returned(self, request, queryset):
        """Mark as returned"""
        updated = queryset.filter(status=ReturnRequest.ReturnStatus.APPROVED).update(
            status=ReturnRequest.ReturnStatus.RETURNED
        )
        self.message_user(request, f'{updated} {_("marked as returned.")}')
    mark_as_returned.short_description = _('Mark as returned')