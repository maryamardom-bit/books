from django.contrib import admin
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum

from .models import Product, Comment, Package


class CommentsInLine(admin.TabularInline):
    model = Comment
    fields = ['author', 'body', 'stars', 'active']
    extra = 0
    readonly_fields = ['datetime_created']


@admin.register(Product)
class ProductAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = [
        'title', 
        'category', 
        'author', 
        'publisher', 
        'price_display',
        'discount_display',
        'weight',
        'active'
    ]
    list_filter = [
        'category', 
        'active', 
        'book_size', 
        'cover_type', 
        'year_of_publication', 
        'datetime_created',
        'discount_percent',
        'discount_start_date',
        'discount_end_date'
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
        (_('Discount Settings'), {
            'fields': (
                'discount_percent',
                'special_price',
                'discount_start_date',
                'discount_end_date',
            ),
            'classes': ('wide',),
            'description': _(
                '🛈 <b>راهنمای تخفیف:</b><br>'
                '• برای تخفیف درصدی: فقط "درصد تخفیف" را وارد کنید<br>'
                '• برای قیمت ویژه: "قیمت ویژه" را وارد کنید (اولویت با قیمت ویژه است)<br>'
                '• برای تخفیف زمان‌دار: تاریخ شروع و پایان را مشخص کنید<br>'
                '• اگر تاریخ مشخص نشود، تخفیف همیشه فعال است'
            )
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
                '<del style="color: #999;">{:}</del> '
                '<span style="color: #28a745; font-weight: bold;">{:}</span>',
                obj.price,
                discounted
            )
        return format_html('<span style="font-weight: bold;">{:}</span>', obj.price)
    price_display.short_description = _('Price (Toman)')
    
    def discount_display(self, obj):
        if obj.is_on_sale():
            percent = obj.get_discount_percent_display()
            savings = obj.get_savings()
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">🏷️ {}% - صرفه‌جویی: {}</span>',
                percent,
                savings
            )
        return '-'
    discount_display.short_description = _('Discount')


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'get_products_count_display',
        'original_price_display',
        'price_display',
        'discount_display',
        'savings_display',
        'stock',
        'stock_display',
        'active',
        'datetime_created'
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
            'description': _('Select the products that belong to this package')
        }),
        (_('Pricing'), {
            'fields': (
                'discount_percent', 
                'manual_price',
                'original_price', 
                'price',
            ),
            'description': _(
                '⚠️ <b>راهنمای قیمت‌گذاری:</b><br>'
                '1️⃣ قیمت اصلی به‌صورت خودکار از مجموع کتاب‌ها محاسبه می‌شود<br>'
                '2️⃣ برای تخفیف درصدی: فقط درصد تخفیف را وارد کنید<br>'
                '3️⃣ برای قیمت دستی: قیمت مورد نظر را در فیلد "قیمت دستی" وارد کنید<br>'
                '4️⃣ فیلد "قیمت نهایی" به‌صورت خودکار تنظیم می‌شود'
            )
        }),
        (_('Stock & Dates'), {
            'fields': ('stock', 'datetime_created', 'datetime_modified'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['datetime_created', 'datetime_modified', 'original_price', 'price']
    
    def get_products_count_display(self, obj):
        count = obj.get_products_count()
        return format_html('<span style="font-weight: bold;">📚 {}</span>', count)
    get_products_count_display.short_description = _('Books')
    
    def original_price_display(self, obj):
        if obj.original_price:
            return format_html(
                '<span style="color: #999; text-decoration: line-through;">{:} تومان</span>',
                obj.original_price
            )
        return '-'
    original_price_display.short_description = _('Original Price')
    
    def price_display(self, obj):
        if obj.price:
            if obj.manual_price and obj.manual_price > 0:
                return format_html(
                    '<span style="color: #8e44ad; font-weight: bold; font-size: 14px;">{:} تومان ✏️</span>',
                    obj.price
                )
            elif obj.discount_percent > 0:
                return format_html(
                    '<span style="color: #27ae60; font-weight: bold; font-size: 14px;">{:} تومان 🏷️</span>',
                    obj.price
                )
            else:
                return format_html(
                    '<span style="color: #1a1a2e; font-weight: bold; font-size: 14px;">{:} تومان</span>',
                    obj.price
                )
        return '-'
    price_display.short_description = _('Final Price')
    
    def discount_display(self, obj):
        if obj.discount_percent > 0:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold">% تخفیف</span>',
                obj.discount_percent
            )
        return '-'
    discount_display.short_description = _('Discount')
    
    def savings_display(self, obj):
        savings = obj.calculate_savings()
        if savings > 0:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">صرفه‌جویی {:} تومان</span>',
                savings
            )
        return '-'
    savings_display.short_description = _('Savings')
    
    def stock_display(self, obj):
        """نمایش وضعیت موجودی با آیکون"""
        if obj.stock > 0:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ {:}</span>',
                obj.stock
            )
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">✗ ناموجود</span>'
        )
    stock_display.short_description = _('Stock Status')
    
    def save_model(self, request, obj, form, change):
        """ذخیره مدل با محاسبه خودکار قیمت‌ها"""
        if not change:
            obj.save()
        
        form.save_m2m()
        
        if obj.pk:
            obj.original_price = obj.calculate_original_price()
            
            if obj.manual_price and obj.manual_price > 0:
                obj.price = obj.manual_price
            elif obj.discount_percent > 0 and obj.original_price > 0:
                obj.price = obj.original_price * (1 - obj.discount_percent / 100)
                obj.price = int(obj.price)
            else:
                obj.price = obj.original_price
            
            obj.original_price = int(obj.original_price)
            obj.price = int(obj.price)
            
            obj.save(update_fields=['original_price', 'price'])
    
    actions = ['activate_packages', 'deactivate_packages']
    
    def activate_packages(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} packages activated.')
    activate_packages.short_description = _('Activate selected packages')
    
    def deactivate_packages(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} packages deactivated.')
    deactivate_packages.short_description = _('Deactivate selected packages')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['product', 'author', 'body', 'stars', 'active']
    list_filter = ['active', 'stars', 'datetime_created']
    search_fields = ['author__username', 'product__title', 'body']
    list_editable = ['active']
    list_per_page = 20
    ordering = ['-datetime_created']