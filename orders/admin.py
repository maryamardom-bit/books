from django.contrib import admin
from django.db import models as django_models
from jalali_date.admin import ModelAdminJalaliMixin
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime
import jdatetime

from .models import Order, OrderItem


class OrderItemInLine(admin.TabularInline):
    model = OrderItem
    fields = ['product', 'package', 'quantity', 'price', 'get_weight_display']
    readonly_fields = ['get_weight_display']
    extra = 0

    def get_weight_display(self, obj):
        weight = obj.get_weight()
        if weight > 0:
            return f'{weight} گرم'
        return '-'
    get_weight_display.short_description = 'وزن'


@admin.register(Order)
class OrderAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = [
        'id', 'user', 'first_name', 'last_name', 'phone_number',
        'total_price_display', 'total_weight_display', 'is_paid',
        'datetime_created_jalali',  # ← نمایش شمسی
    ]
    list_filter = ['is_paid', 'datetime_created']
    search_fields = ['user__username', 'first_name', 'last_name', 'phone_number']
    readonly_fields = ['datetime_created', 'datetime_modified', 'total_price', 'total_weight']
    list_per_page = 20

    fieldsets = (
        ('User Info', {'fields': ('user', 'first_name', 'last_name', 'phone_number')}),
        ('Address', {'fields': ('address', 'order_notes')}),
        ('Payment', {'fields': ('is_paid', 'total_price', 'total_weight')}),
        ('Dates', {'fields': ('datetime_created', 'datetime_modified'), 'classes': ('collapse',)}),
    )

    inlines = [OrderItemInLine]

    formfield_overrides = {
        django_models.DateField: {'widget': AdminJalaliDateWidget},
        django_models.DateTimeField: {'widget': AdminSplitJalaliDateTime},
    }

    def total_price_display(self, obj):
        return f'{obj.total_price:,} تومان'
    total_price_display.short_description = 'مبلغ کل'

    def total_weight_display(self, obj):
        if obj.total_weight > 0:
            return f'{obj.total_weight:,} گرم'
        return '-'
    total_weight_display.short_description = 'وزن کل'

    def datetime_created_jalali(self, obj):
        """نمایش تاریخ شمسی با ساعت"""
        if obj.datetime_created:
            jalali_date = jdatetime.datetime.fromgregorian(datetime=obj.datetime_created)
            return jalali_date.strftime('%Y/%m/%d %H:%M')
        return '-'
    datetime_created_jalali.short_description = 'تاریخ ایجاد'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'get_item_title', 'quantity', 'price', 'get_weight_display']
    list_filter = ['order__is_paid']
    search_fields = ['order__id', 'product__title', 'package__title']
    list_per_page = 20

    def get_item_title(self, obj):
        return obj.get_title()
    get_item_title.short_description = 'عنوان'

    def get_weight_display(self, obj):
        weight = obj.get_weight()
        if weight > 0:
            return f'{weight} گرم'
        return '-'
    get_weight_display.short_description = 'وزن'