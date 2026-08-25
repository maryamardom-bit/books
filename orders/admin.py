from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db import models as django_models
from jalali_date.admin import ModelAdminJalaliMixin
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime
import jdatetime

from .models import Order, OrderItem, ReturnRequest
from services.sms import SMSService


class OrderItemInLine(admin.TabularInline):
    model = OrderItem
    fields = ['product', 'package', 'quantity', 'price', 'get_weight_display']
    readonly_fields = ['get_weight_display']
    extra = 0

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
        'total_price_display', 'total_weight_display', 'is_paid',
        'datetime_created_jalali',
    ]
    list_filter = ['is_paid', 'datetime_created']
    search_fields = ['user__username', 'first_name', 'last_name', 'phone_number']
    readonly_fields = ['datetime_created', 'datetime_modified', 'total_price', 'total_weight']
    list_per_page = 20

    fieldsets = (
        (_('User Info'), {'fields': ('user', 'first_name', 'last_name', 'phone_number')}),
        (_('Address'), {'fields': ('address', 'order_notes')}),
        (_('Payment'), {'fields': ('is_paid', 'total_price', 'total_weight')}),
        (_('Dates'), {'fields': ('datetime_created', 'datetime_modified'), 'classes': ('collapse',)}),
    )

    inlines = [OrderItemInLine]

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
        count = 0
        for return_request in queryset:
            if return_request.status == ReturnRequest.ReturnStatus.PENDING:
                return_request.status = ReturnRequest.ReturnStatus.APPROVED
                return_request.save()

                # Restock items
                for item in return_request.order.items.all():
                    if item.product:
                        item.product.increase_stock(item.quantity)
                    elif item.package:
                        item.package.stock += item.quantity
                        item.package.save(update_fields=['stock'])

                # Refund to wallet
                return_request.user.wallet_balance += return_request.order.total_price
                return_request.user.save(update_fields=['wallet_balance'])

                # Send SMS confirmation
                if return_request.user.phone_number:
                    SMSService.send_return_confirmation_sms(
                        return_request.user,
                        return_request.order,
                        return_request
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