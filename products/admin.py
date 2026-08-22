from django.contrib import admin
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin
from django.utils.translation import gettext_lazy as _

from .models import Product, Comment, Package


class CommentsInLine(admin.TabularInline):
    model = Comment
    fields = ['author', 'body', 'stars', 'active']
    extra = 0
    readonly_fields = ['datetime_created']
    can_delete = True
    show_change_link = True


@admin.register(Product)
class ProductAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = [
        'title',
        'category',
        'author',
        'publisher',
        'price_display',
        'discount_display',
        'stock_display',
        'weight',
        'active',
    ]
    list_filter = [
        'category',
        'active',
        'book_size',
        'cover_type',
        'year_of_publication',
        'datetime_created',
        'discount_percent',
    ]
    search_fields = ['title', 'description', 'author', 'publisher', 'isbn']
    list_editable = ['active']
    readonly_fields = ['datetime_created', 'datetime_modified']
    list_per_page = 20

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'category', 'description', 'price', 'image')
        }),
        (_('Book Details'), {
            'fields': (
                'author', 'edition', 'book_size', 'number_of_pages',
                'cover_type', 'weight', 'publication_date', 'printing_series',
                'year_of_publication', 'publisher', 'isbn'
            ),
            'classes': ('wide', 'extrapretty'),
        }),
        (_('Stock Management'), {
            'fields': ('stock', 'reserved_stock'),
            'classes': ('wide',),
        }),
        (_('Discount Settings'), {
            'fields': (
                'discount_percent',
                'special_price',
                'discount_start_date',
                'discount_end_date',
            ),
            'classes': ('wide',),
        }),
        (_('Status & Dates'), {
            'fields': ('active', 'datetime_created', 'datetime_modified'),
            'classes': ('collapse',),
        }),
    )

    inlines = [CommentsInLine]

    def price_display(self, obj):
        if obj.is_on_sale():
            discounted = obj.get_discounted_price()
            return format_html(
                '<del style="color: #999;">{} </del> <span style="color: #28a745; font-weight: bold;">{}</span>',
                obj.price,
                discounted
            )
        return format_html('<span style="font-weight: bold;">{}</span>', obj.price)
    price_display.short_description = _('Price')

    def discount_display(self, obj):
        if obj.is_on_sale():
            percent = obj.get_discount_percent_display()
            savings = obj.get_savings()
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">{}% - {}</span>',
                percent,
                savings
            )
        return '-'
    discount_display.short_description = _('Discount')

    def stock_display(self, obj):
        available = obj.available_stock
        if obj.stock == 0:
            return format_html('<span style="color: #dc3545;">Out</span>')
        elif available == 0:
            return format_html('<span style="color: #ffc107;">Reserved</span>')
        elif available < 5:
            return format_html('<span style="color: #fd7e14;">{} left</span>', available)
        else:
            return format_html('<span style="color: #28a745;">{} available</span>', available)
    stock_display.short_description = _('Stock')


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'get_products_count_display',
        'original_price_display',
        'price_display',
        'discount_display',
        'savings_display',
        'total_weight_display',
        'stock',
        'active',
    ]

    list_filter = ['active', 'datetime_created', 'discount_percent']
    search_fields = ['title', 'description', 'products__title']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('products',)
    list_editable = ['active', 'stock']

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'slug', 'description', 'image', 'active')
        }),
        (_('Products in this Package'), {
            'fields': ('products',),
        }),
        (_('Pricing'), {
            'fields': (
                'discount_percent',
                'manual_price',
                'original_price',
                'price',
            ),
        }),
        (_('Stock & Dates'), {
            'fields': ('stock', 'datetime_created', 'datetime_modified'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['datetime_created', 'datetime_modified', 'original_price', 'price']

    def get_products_count_display(self, obj):
        count = obj.get_products_count()
        return format_html('<b>{}</b>', count)
    get_products_count_display.short_description = _('Books')

    def original_price_display(self, obj):
        if obj.original_price:
            return format_html(
                '<span style="color: #999; text-decoration: line-through;">{}</span>',
                obj.original_price
            )
        return '-'
    original_price_display.short_description = _('Original')

    def price_display(self, obj):
        if obj.price:
            return format_html('<b>{}</b>', obj.price)
        return '-'
    price_display.short_description = _('Price')

    def discount_display(self, obj):
        if obj.discount_percent > 0:
            return format_html('<span style="color: #dc3545;">{}%</span>', obj.discount_percent)
        return '-'
    discount_display.short_description = _('Discount')

    def savings_display(self, obj):
        savings = obj.calculate_savings()
        if savings > 0:
            return format_html('<span style="color: #28a745;">{}</span>', savings)
        return '-'
    savings_display.short_description = _('Savings')

    def total_weight_display(self, obj):
        weight = obj.get_total_weight()
        if weight > 0:
            return format_html('<span>{}</span>', weight)
        return '-'
    total_weight_display.short_description = _('Weight')

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
class CommentAdmin(admin.ModelAdmin):
    list_display = ['product', 'author', 'body_preview', 'stars', 'active', 'datetime_created']
    list_filter = ['active', 'stars', 'datetime_created']
    search_fields = ['author__username', 'product__title', 'body']
    list_editable = ['active']  # ← می‌تونی از همین لیست تیک فعال/غیرفعال بزنی
    list_per_page = 20
    ordering = ['-datetime_created']
    
    def body_preview(self, obj):
        return obj.body[:50] + '...' if len(obj.body) > 50 else obj.body
    body_preview.short_description = 'متن'
    list_display = ['product', 'author', 'body', 'stars', 'active', 'datetime_created']
    list_filter = ['active', 'stars', 'datetime_created']
    search_fields = ['author__username', 'product__title', 'body']
    list_editable = ['active']  # ← می‌تونی مستقیم از لیست تیک بزنی
    list_per_page = 20
    ordering = ['-datetime_created']
    
    actions = ['approve_comments', 'reject_comments']
    
    def approve_comments(self, request, queryset):
        """تایید گروهی نظرات"""
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} نظر تایید شد.')
    approve_comments.short_description = 'تایید نظرات انتخاب شده'
    
    def reject_comments(self, request, queryset):
        """رد گروهی نظرات"""
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} نظر رد شد.')
    reject_comments.short_description = 'رد نظرات انتخاب شده'
    list_display = ['product', 'author', 'body', 'stars', 'active', 'datetime_created']
    list_filter = ['active', 'stars', 'datetime_created']
    search_fields = ['author__username', 'product__title', 'body']
    list_editable = ['active']
    list_per_page = 20
    ordering = ['-datetime_created']