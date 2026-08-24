from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db import models as django_models
from jalali_date.admin import ModelAdminJalaliMixin
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime
import jdatetime

from .models import Product, Comment, Package
from .widgets import CustomJalaliDateTimeWidget


class CommentsInLine(admin.TabularInline):
    model = Comment
    fields = ['author', 'body', 'stars', 'active']
    extra = 0
    readonly_fields = ['datetime_created']


@admin.register(Product)
class ProductAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'publisher', 'price_display', 'discount_display', 'stock', 'active']
    list_filter = ['category', 'active', 'book_size', 'cover_type', 'year_of_publication', 'datetime_created']
    search_fields = ['title', 'description', 'author', 'publisher', 'isbn']
    list_editable = ['active']
    readonly_fields = ['datetime_created', 'datetime_modified']
    list_per_page = 20

    fieldsets = (
        (_('Basic Information'), {'fields': ('title', 'category', 'description', 'price', 'image')}),
        (_('Book Details'), {'fields': ('author', 'edition', 'book_size', 'number_of_pages', 'cover_type', 'weight', 'publication_date', 'printing_series', 'year_of_publication', 'publisher', 'isbn')}),
        (_('Stock Management'), {'fields': ('stock', 'reserved_stock')}),
        (_('Discount Settings'), {'fields': ('discount_percent', 'special_price', 'discount_start_date', 'discount_end_date')}),
        (_('Status & Dates'), {'fields': ('active', 'datetime_created', 'datetime_modified'), 'classes': ('collapse',)}),
    )

    inlines = [CommentsInLine]
    
    formfield_overrides = {
        django_models.DateTimeField: {'widget': CustomJalaliDateTimeWidget},
    }

    def price_display(self, obj):
        if obj.is_on_sale():
            return format_html('<del style="color:#999;">{}</del> <b style="color:#28a745;">{}</b>', obj.price, obj.get_discounted_price())
        return format_html('<b>{}</b>', obj.price)
    price_display.short_description = _('Price')

    def discount_display(self, obj):
        if obj.is_on_sale():
            return format_html('<span style="color:#dc3545;">{}% - {}</span>', obj.get_discount_percent_display(), obj.get_savings())
        return '-'
    discount_display.short_description = _('Discount')


@admin.register(Package)
class PackageAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['title', 'get_products_count_display', 'original_price_display', 'price_display', 'discount_display', 'stock', 'active']
    list_filter = ['active', 'datetime_created']
    search_fields = ['title', 'description', 'products__title']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('products',)
    list_editable = ['active', 'stock']
    readonly_fields = ['datetime_created', 'datetime_modified', 'original_price', 'price']

    fieldsets = (
        (_('Basic Information'), {'fields': ('title', 'slug', 'description', 'image', 'active')}),
        (_('Products'), {'fields': ('products',)}),
        (_('Pricing'), {'fields': ('discount_percent', 'manual_price', 'original_price', 'price')}),
        (_('Stock & Dates'), {'fields': ('stock', 'datetime_created', 'datetime_modified'), 'classes': ('collapse',)}),
    )
    
    formfield_overrides = {
        django_models.DateTimeField: {'widget': CustomJalaliDateTimeWidget},
    }

    def get_products_count_display(self, obj):
        return format_html('<b>{}</b>', obj.get_products_count())
    get_products_count_display.short_description = _('Books')

    def original_price_display(self, obj):
        if obj.original_price:
            return format_html('<span style="color:#999; text-decoration:line-through;">{}</span>', obj.original_price)
        return '-'
    original_price_display.short_description = _('Original Price')

    def price_display(self, obj):
        if obj.price:
            return format_html('<b>{}</b>', obj.price)
        return '-'
    price_display.short_description = _('Price')

    def discount_display(self, obj):
        if obj.discount_percent > 0:
            return format_html('<span style="color:#dc3545;">{}%</span>', obj.discount_percent)
        return '-'
    discount_display.short_description = _('Discount')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.save()
        form.save_m2m()
        if obj.pk:
            obj.original_price = obj.calculate_original_price()
            if obj.manual_price and obj.manual_price > 0:
                obj.price = obj.manual_price
            elif obj.discount_percent > 0 and obj.original_price > 0:
                obj.price = int(obj.original_price * (1 - obj.discount_percent / 100))
            else:
                obj.price = obj.original_price
            obj.original_price = int(obj.original_price)
            obj.price = int(obj.price)
            obj.save(update_fields=['original_price', 'price'])


@admin.register(Comment)
class CommentAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['product', 'author', 'body', 'stars', 'active', 'datetime_created']
    list_filter = ['active', 'stars', 'datetime_created']
    search_fields = ['author__username', 'product__title', 'body']
    list_editable = ['active']
    list_per_page = 20
    ordering = ['-datetime_created']