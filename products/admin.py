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


class PackageInline(admin.TabularInline):
    """نمایش پکیج‌های مربوط به هر کتاب"""
    model = Package.products.through
    extra = 0
    verbose_name = _('package')
    verbose_name_plural = _('packages')
    fields = ['package_link', 'package_price']
    readonly_fields = ['package_link', 'package_price']
    
    def package_link(self, obj):
        try:
            if obj.package:
                url = admin.utils.admin_urlname('package', 'change', obj.package.id)
                return format_html('<a href="{}">{}</a>', url, obj.package.title)
        except:
            pass
        return '-'
    package_link.short_description = _('Package')
    
    def package_price(self, obj):
        try:
            if obj.package and obj.package.price is not None:
                return f"${float(obj.package.price):,.0f}"
        except (TypeError, ValueError, AttributeError):
            pass
        return '-'
    package_price.short_description = _('Package Price')


@admin.register(Product)
class ProductAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'publisher', 'price', 'active']
    list_filter = ['category', 'active', 'book_size', 'cover_type', 'year_of_publication', 'datetime_created']
    search_fields = ['title', 'description', 'author', 'publisher', 'isbn']
    list_editable = ['price', 'active']
    readonly_fields = ['datetime_created', 'datetime_modified']
    list_per_page = 20
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'title', 
                'category', 
                'description', 
                'price', 
                'image'
            )
        }),
        (_('Book Details'), {
            'fields': (
                'author',
                'edition',
                'book_size',
                'number_of_pages', 
                'cover_type',
                'weight', 
                'publication_date',
                'printing_series',
                'year_of_publication',
                'publisher',
                'isbn', 
            ),
            'classes': ('wide', 'extrapretty'),
        }),
        (_('Status & Dates'), {
            'fields': (
                'active', 
                'datetime_created', 
                'datetime_modified'
            ),
            'classes': ('collapse',),
        }),
    )
    
    inlines = [
        CommentsInLine,
        PackageInline,
    ]


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = [
        'title', 
        'get_products_count_display', 
        'original_price_display',
        'price_display', 
        'discount_percent_display',
        'savings_display',
        'active',
        'datetime_created'
    ]
    
    list_filter = ['active', 'datetime_created']
    search_fields = ['title', 'description', 'products__title']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('products',)
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'slug', 'description', 'image')
        }),
        (_('Products'), {
            'fields': ('products',),
            'description': _('Select the products that belong to this package')
        }),
        (_('Pricing'), {
            'fields': ('price', 'original_price', 'discount_percent'),
            'description': _('Set the package price. Original price is auto-calculated.')
        }),
        (_('Status'), {
            'fields': ('active', 'datetime_created', 'datetime_modified'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['datetime_created', 'datetime_modified', 'original_price']
    
    def get_products_count_display(self, obj):
        """نمایش تعداد کتاب‌ها"""
        try:
            count = obj.get_products_count()
            if isinstance(count, (int, float)):
                return format_html('<span style="font-weight: bold;">{}</span>', count)
        except (TypeError, ValueError, AttributeError):
            pass
        return format_html('<span style="font-weight: bold;">0</span>')
    get_products_count_display.short_description = _('Products Count')
    
    def original_price_display(self, obj):
        """نمایش قیمت اصلی با فرمت"""
        try:
            if obj.original_price is not None:
                price = float(obj.original_price)
                if isinstance(price, (int, float)):
                    return f"${price:,.0f}"
        except (TypeError, ValueError, AttributeError):
            pass
        return '-'
    original_price_display.short_description = _('Original Price')
    
    def price_display(self, obj):
        """نمایش قیمت پکیج با فرمت و رنگ"""
        try:
            if obj.price is not None:
                price = float(obj.price)
                if isinstance(price, (int, float)):
                    color = '#28a745' if obj.discount_percent > 0 else '#007bff'
                    return format_html(
                        '<span style="color: {}; font-weight: bold;">${:,.0f}</span>',
                        color,
                        price
                    )
        except (TypeError, ValueError, AttributeError):
            pass
        return '-'
    price_display.short_description = _('Package Price')
    
    def discount_percent_display(self, obj):
        """نمایش درصد تخفیف"""
        try:
            if obj.discount_percent > 0:
                return format_html(
                    '<span style="color: #dc3545; font-weight: bold;">{}%</span>',
                    obj.discount_percent
                )
        except (TypeError, ValueError, AttributeError):
            pass
        return '-'
    discount_percent_display.short_description = _('Discount')
    
    def savings_display(self, obj):
        """نمایش میزان صرفه‌جویی"""
        try:
            savings = obj.get_savings()
            if savings > 0 and isinstance(savings, (int, float)):
                return format_html(
                    '<span style="color: #28a745; font-weight: bold;">${:,.0f}</span>',
                    savings
                )
        except (TypeError, ValueError, AttributeError):
            pass
        return '-'
    savings_display.short_description = _('Savings')
    
    def save_model(self, request, obj, form, change):
        """ذخیره مدل با محاسبه خودکار قیمت‌ها"""
        try:
            if change:
                obj.original_price = obj.calculate_original_price()
                if obj.discount_percent > 0 and obj.original_price:
                    obj.price = obj.original_price * (1 - obj.discount_percent / 100)
                elif not obj.price and obj.original_price:
                    obj.price = obj.original_price
        except Exception:
            obj.price = 0
            obj.original_price = 0
        super().save_model(request, obj, form, change)
    
    actions = ['activate_packages', 'deactivate_packages', 'apply_discount_10']
    
    def activate_packages(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} packages activated.')
    activate_packages.short_description = _('Activate selected packages')
    
    def deactivate_packages(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} packages deactivated.')
    deactivate_packages.short_description = _('Deactivate selected packages')
    
    def apply_discount_10(self, request, queryset):
        count = 0
        for package in queryset:
            try:
                package.discount_percent = 10
                package.save()
                count += 1
            except Exception:
                pass
        self.message_user(request, f'10% discount applied to {count} packages.')
    apply_discount_10.short_description = _('apply 10 percent discount')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['product', 'author', 'body', 'stars', 'active']
    list_filter = ['active', 'stars', 'datetime_created']
    search_fields = ['author__username', 'product__title', 'body']
    list_editable = ['active']
    list_per_page = 20
    ordering = ['-datetime_created']