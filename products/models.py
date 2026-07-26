from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from ckeditor.fields import RichTextField
from django.core.validators import MinValueValidator

class Product(models.Model):

    class Category(models.TextChoices):
        BUSINESS = 'BUSINESS', _('BUSINESS')
        ARCH_DESIGN = 'ARCH_DESIGN', _('ARCH_DESIGN')
        INTERIOR = 'INTERIOR', _('INTERIOR')
        URBAN = 'URBAN', _('URBAN')
        LANDSCAPE = 'LANDSCAPE', _('LANDSCAPE')
        DESIGN_GUIDE = 'DESIGN_GUIDE', _('DESIGN_GUIDE')
        HISTORY = 'HISTORY', _('HISTORY')
        DESIGN_BASICS = 'DESIGN_BASICS', _('DESIGN_BASICS')
        DIGITAL = 'DIGITAL', _('DIGITAL')
        SUSTAIN = 'SUSTAIN', _('SUSTAIN')
        SAMPLES = 'SAMPLES', _('SAMPLES')
        OTHER = 'OTHER', _('OTHER')
        PACKAGES = 'PACKAGES', _('PACKAGES')

    class BookSize(models.TextChoices):
        RAGHIEI = 'raghiei', _('رقعی')
        VAZEHI = 'vazehi', _('وزیری')
        JEYBI = 'jeybi', _('جیبی')
        RAHLEI = 'rahlei', _('رحلی')
        OTHER = 'other', _('سایر')
   
    class CoverType(models.TextChoices):
        SHOMIZ = 'shomiz', _('شومیز')
        GARD = 'gard', _('گالینگور')
        OTHER = 'other', _('سایر')

    title = models.CharField(max_length=100, verbose_name=_('product_title'))
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
        verbose_name=_('product_category')
    )
    description = RichTextField(verbose_name=_('description'))
    price = models.PositiveIntegerField(default=0, verbose_name=_('price'))
    active = models.BooleanField(default=True, verbose_name=_('active'))
    image = models.ImageField(upload_to='product/product_cover/', blank=True, verbose_name=_('image'))
    author = models.CharField(max_length=200, blank=True, verbose_name=_('author'))
    publisher = models.CharField(max_length=200, blank=True, verbose_name=_('publisher'))
    isbn = models.CharField(max_length=20, blank=True, verbose_name=_('isbn'))
    year_of_publication = models.IntegerField(null=True, blank=True, verbose_name=_('year_of_publication'))
    edition = models.CharField(max_length=50, blank=True, verbose_name=_('edition'))
    number_of_pages = models.IntegerField(null=True, blank=True, verbose_name=_('number_of_pages'))
    book_size = models.CharField(max_length=20, choices=BookSize.choices, blank=True, null=True, verbose_name=_('book_size'))
    cover_type = models.CharField(max_length=20, choices=CoverType.choices, blank=True, null=True, verbose_name=_('cover_type'))
    publication_date = models.IntegerField(null=True, blank=True, verbose_name=_('publication_date'))
    printing_series=models.CharField(null=True, blank=True, verbose_name=_('printing_series'))
    weight= models.IntegerField(null=True, blank=True, verbose_name=_('weight'))

   
    datetime_created = models.DateTimeField(default=timezone.now, verbose_name=_('datetime_created'))
    datetime_modified = models.DateTimeField(auto_now=True, verbose_name=_('datetime_modified'))

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:product_detail', args=[self.pk])


class ActiveCommentsManager(models.Manager):
    def get_queryset(self):
        return super(ActiveCommentsManager, self).get_queryset().filter(active=True)


class Comment(models.Model):
    PRODUCT_STARS = [
        (1, _('Very_Bad')),
        (2, _('Bad')), 
        (3, _('Normal')), 
        (4, _('Good')), 
        (5, _('Perfect')),  
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments', verbose_name=_('Comment_Product'))
    author = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='comment_author',
    )
    
    body = models.TextField(verbose_name=_('Comment_Text'))
    stars = models.IntegerField(choices=PRODUCT_STARS, verbose_name=_('What_is_your_score?'))

    datetime_created = models.DateTimeField(auto_now_add=True)
    detetime_modified = models.DateTimeField(auto_now=True)

    active = models.BooleanField(default=True, verbose_name=_('Comment_Active'))

    objects = models.Manager()
    active_comments_manager = ActiveCommentsManager()

    def get_absolute_url(self):
        return reverse('product_detail', args=[self.product.id])
    


class Package(models.Model):
    """
    مدل پکیج‌ها و مجموعه‌های کتاب
    """
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=200, unique=True, allow_unicode=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(_('image'), upload_to='packages/', blank=True, null=True)
    
    # کتاب‌های موجود در این پکیج
    products = models.ManyToManyField(
        'Product',
        related_name='packages',
        verbose_name=_('products'),
        limit_choices_to={'active': True},
        blank=True
    )
    
    # قیمت اصلی (مجموع قیمت کتاب‌ها)
    original_price = models.DecimalField(
        _('original price'),
        max_digits=10,
        decimal_places=0,
        default=0,
        help_text=_('Sum of all product prices (auto-calculated)')
    )
    
    # قیمت نهایی با تخفیف
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Final price after discount')
    )
    
    # درصد تخفیف
    discount_percent = models.PositiveSmallIntegerField(
        _('discount percent'),
        default=0,
        help_text=_('Discount percentage for this package')
    )
    
    # موجودی
    stock = models.PositiveIntegerField(
        _('stock'),
        default=0,
        help_text=_('Available stock for this package')
    )
    
    active = models.BooleanField(_('active'), default=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    datetime_modified = models.DateTimeField(_('modified'), auto_now=True)
    
    class Meta:
        verbose_name = _('package')
        verbose_name_plural = _('packages')
        ordering = ['-datetime_created']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:package_detail', args=[self.slug])
    
    def calculate_original_price(self):
        """محاسبه مجموع قیمت کتاب‌های موجود در پکیج"""
        try:
            return sum(product.price for product in self.products.all())
        except Exception:
            return 0
    
    def get_products_count(self):
        """تعداد کتاب‌های موجود در پکیج"""
        try:
            return self.products.count()
        except Exception:
            return 0
    
    def get_savings(self):
        """میزان صرفه‌جویی"""
        try:
            return float(self.original_price) - float(self.price)
        except Exception:
            return 0
    
    def is_in_stock(self):
        """بررسی موجودی"""
        return self.stock > 0
    
    def save(self, *args, **kwargs):
        # اگر پکیج جدید است، فقط ذخیره کن
        if not self.pk:
            super().save(*args, **kwargs)
            return
        
        # محاسبه قیمت‌ها
        try:
            self.original_price = self.calculate_original_price()
            
            if self.discount_percent > 0 and self.original_price > 0:
                self.price = self.original_price * (1 - self.discount_percent / 100)
            else:
                self.price = self.original_price
                
            self.price = int(self.price)
            self.original_price = int(self.original_price)
        except Exception:
            self.price = 0
            self.original_price = 0
        
        super().save(*args, **kwargs)
    """
    مدل پکیج‌ها و مجموعه‌های کتاب
    """
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=200, unique=True, allow_unicode=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(_('image'), upload_to='packages/', blank=True, null=True)
    
    # کتاب‌های موجود در این پکیج
    products = models.ManyToManyField(
        'Product',
        related_name='packages',
        verbose_name=_('products'),
        limit_choices_to={'active': True},
        blank=True
    )
    
    # قیمت اصلی (مجموع قیمت کتاب‌ها)
    original_price = models.DecimalField(
        _('original price'),
        max_digits=10,
        decimal_places=0,
        default=0,  # مقدار پیش‌فرض
        help_text=_('Sum of all product prices (auto-calculated)')
    )
    
    # قیمت نهایی با تخفیف
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=0,
        default=0,  # مقدار پیش‌فرض - این مهم است!
        validators=[MinValueValidator(0)],
        help_text=_('Final price after discount')
    )
    
    # درصد تخفیف
    discount_percent = models.PositiveSmallIntegerField(
        _('discount percent'),
        default=0,
        help_text=_('Discount percentage for this package')
    )
    
    # موجودی
    stock = models.PositiveIntegerField(
        _('stock'),
        default=0,
        help_text=_('Available stock for this package')
    )
    
    active = models.BooleanField(_('active'), default=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    datetime_modified = models.DateTimeField(_('modified'), auto_now=True)
    
    class Meta:
        verbose_name = _('package')
        verbose_name_plural = _('packages')
        ordering = ['-datetime_created']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:package_detail', args=[self.slug])
    
    def calculate_original_price(self):
        """محاسبه مجموع قیمت کتاب‌های موجود در پکیج"""
        try:
            if self.pk:
                return sum(product.price for product in self.products.all())
            return 0
        except Exception:
            return 0
    
    def get_products_count(self):
        """تعداد کتاب‌های موجود در پکیج"""
        try:
            return self.products.count()
        except Exception:
            return 0
    
    def get_savings(self):
        """میزان صرفه‌جویی"""
        try:
            return self.original_price - self.price
        except Exception:
            return 0
    
    def is_in_stock(self):
        """بررسی موجودی"""
        return self.stock > 0
    
    def save(self, *args, **kwargs):
        try:
            # فقط در صورتی که شیء قبلاً ذخیره شده باشد
            if self.pk:
                # محاسبه قیمت اصلی
                self.original_price = self.calculate_original_price()
                
                # محاسبه قیمت نهایی با تخفیف
                if self.discount_percent > 0 and self.original_price > 0:
                    self.price = self.original_price * (1 - self.discount_percent / 100)
                else:
                    self.price = self.original_price
                    
                # گرد کردن به عدد صحیح
                self.price = int(self.price)
                self.original_price = int(self.original_price)
            else:
                # برای ایجاد جدید، مقدار پیش‌فرض بگذار
                self.original_price = 0
                self.price = 0
                
        except Exception as e:
            self.price = 0
            self.original_price = 0
            
        super().save(*args, **kwargs)
    """
    مدل پکیج‌ها و مجموعه‌های کتاب
    """
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=200, unique=True, allow_unicode=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(_('image'), upload_to='packages/', blank=True, null=True)
    
    # کتاب‌های موجود در این پکیج
    products = models.ManyToManyField(
        'Product',
        related_name='packages',
        verbose_name=_('products'),
        limit_choices_to={'active': True}
    )
    
    # قیمت اصلی (مجموع قیمت کتاب‌ها)
    original_price = models.DecimalField(
        _('original price'),
        max_digits=10,
        decimal_places=0,
        default=0,
        help_text=_('Sum of all product prices (auto-calculated)')
    )
    
    # قیمت نهایی با تخفیف
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Final price after discount')
    )
    
    # درصد تخفیف
    discount_percent = models.PositiveSmallIntegerField(
        _('discount percent'),
        default=0,
        help_text=_('Discount percentage for this package')
    )
    
    # موجودی
    stock = models.PositiveIntegerField(
        _('stock'),
        default=0,
        help_text=_('Available stock for this package')
    )
    
    active = models.BooleanField(_('active'), default=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    datetime_modified = models.DateTimeField(_('modified'), auto_now=True)
    
    class Meta:
        verbose_name = _('package')
        verbose_name_plural = _('packages')
        ordering = ['-datetime_created']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:package_detail', args=[self.slug])
    
    def calculate_original_price(self):
        """محاسبه مجموع قیمت کتاب‌های موجود در پکیج"""
        try:
            return sum(product.price for product in self.products.all())
        except Exception:
            return 0
    
    def get_products_count(self):
        """تعداد کتاب‌های موجود در پکیج"""
        try:
            return self.products.count()
        except Exception:
            return 0
    
    def get_savings(self):
        """میزان صرفه‌جویی"""
        try:
            return self.original_price - self.price
        except Exception:
            return 0
    
    def is_in_stock(self):
        """بررسی موجودی"""
        return self.stock > 0
    
    def save(self, *args, **kwargs):
        try:
            # فقط در صورتی که شیء قبلاً ذخیره شده باشد (pk وجود دارد)
            if self.pk:
                # محاسبه قیمت اصلی
                self.original_price = self.calculate_original_price()
                
                # محاسبه قیمت نهایی با تخفیف
                if self.discount_percent > 0 and self.original_price > 0:
                    self.price = self.original_price * (1 - self.discount_percent / 100)
                else:
                    self.price = self.original_price
                    
                # گرد کردن به عدد صحیح
                self.price = int(self.price)
                self.original_price = int(self.original_price)
            else:
                # برای ایجاد جدید، مقدار پیش‌فرض بگذار
                self.original_price = 0
                self.price = 0
                
        except Exception:
            self.price = 0
            self.original_price = 0
            
        super().save(*args, **kwargs)
    """
    مدل پکیج‌های کتاب‌های معماری
    """
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=200, unique=True, allow_unicode=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(_('image'), upload_to='packages/', blank=True, null=True)
    
    # کتاب‌های موجود در این پکیج
    products = models.ManyToManyField(
        'Product',
        related_name='packages',
        verbose_name=_('products'),
        limit_choices_to={'active': True},
        blank=True  # اضافه کردن blank=True
    )
    
    # قیمت پکیج (می‌تواند تخفیف داشته باشد)
    price = models.DecimalField(
        _('price'), 
        max_digits=10, 
        decimal_places=2,
        default=0,  # اضافه کردن default
        validators=[MinValueValidator(0)],
        help_text=_('Total price for this package')
    )
    
    # قیمت اصلی (مجموع قیمت کتاب‌ها - برای نمایش تخفیف)
    original_price = models.DecimalField(
        _('original price'), 
        max_digits=10, 
        decimal_places=2,
        default=0,  # اضافه کردن default
        validators=[MinValueValidator(0)],
        help_text=_('Sum of all product prices (auto-calculated)')
    )
    
    # تخفیف درصدی
    discount_percent = models.PositiveSmallIntegerField(
        _('discount percent'),
        default=0,
        help_text=_('Discount percentage for this package')
    )
    
    active = models.BooleanField(_('active'), default=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    datetime_modified = models.DateTimeField(_('modified'), auto_now=True)
    
    class Meta:
        verbose_name = _('package')
        verbose_name_plural = _('packages')
        ordering = ['-datetime_created']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:package_detail', args=[self.slug])
    
    def calculate_original_price(self):
        """محاسبه مجموع قیمت کتاب‌های موجود در پکیج"""
        try:
            total = sum(product.price for product in self.products.all())
            return total
        except Exception:
            return 0
    
    def get_products_count(self):
        """تعداد کتاب‌های موجود در پکیج"""
        try:
            return self.products.count()
        except Exception:
            return 0
    
    def get_savings(self):
        """میزان صرفه‌جویی"""
        try:
            if self.original_price and self.price:
                return float(self.original_price) - float(self.price)
        except Exception:
            pass
        return 0
    
    def save(self, *args, **kwargs):
        try:
            # محاسبه خودکار قیمت اصلی (فقط در صورت وجود pk)
            if self.pk:
                self.original_price = self.calculate_original_price()
            
            # اگر تخفیف درصدی تنظیم شده، قیمت را محاسبه کن
            if self.discount_percent > 0 and self.original_price:
                self.price = self.original_price * (1 - self.discount_percent / 100)
            elif not self.price and self.original_price:
                self.price = self.original_price
            elif not self.price:
                self.price = 0
                
        except Exception:
            self.price = 0
            self.original_price = 0
            
        super().save(*args, **kwargs)
    # ... فیلدها ...

    def get_products_count(self):
        """تعداد کتاب‌های موجود در پکیج"""
        try:
            return self.products.count()
        except:
            return 0

    def get_savings(self):
        """میزان صرفه‌جویی"""
        try:
            if self.original_price and self.price:
                return float(self.original_price) - float(self.price)
        except:
            pass
        return 0

    def save(self, *args, **kwargs):
        try:
            # محاسبه خودکار قیمت اصلی
            if self.pk:
                self.original_price = self.calculate_original_price()
            
            # اگر تخفیف درصدی تنظیم شده، قیمت را محاسبه کن
            if self.discount_percent > 0 and self.original_price:
                self.price = self.original_price * (1 - self.discount_percent / 100)
            elif not self.price and self.original_price:
                self.price = self.original_price
            elif not self.price:
                self.price = 0
        except:
            self.price = 0
            self.original_price = 0
            
        super().save(*args, **kwargs)
    """
    مدل پکیج‌های کتاب‌های معماری
    """
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=200, unique=True, allow_unicode=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(_('image'), upload_to='packages/', blank=True, null=True)
    
    # کتاب‌های موجود در این پکیج
    products = models.ManyToManyField(
        'Product',
        related_name='packages',
        verbose_name=_('products'),
        limit_choices_to={'active': True}
    )
    
    # قیمت پکیج (می‌تواند تخفیف داشته باشد)
    price = models.DecimalField(
        _('price'), 
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Total price for this package')
    )
    
    # قیمت اصلی (مجموع قیمت کتاب‌ها - برای نمایش تخفیف)
    original_price = models.DecimalField(
        _('original price'), 
        max_digits=10, 
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        help_text=_('Sum of all product prices (auto-calculated)')
    )
    
    # تخفیف درصدی
    discount_percent = models.PositiveSmallIntegerField(
        _('discount percent'),
        default=0,
        help_text=_('Discount percentage for this package')
    )
    
    active = models.BooleanField(_('active'), default=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    datetime_modified = models.DateTimeField(_('modified'), auto_now=True)
    
    class Meta:
        verbose_name = _('package')
        verbose_name_plural = _('packages')
        ordering = ['-datetime_created']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:package_detail', args=[self.slug])
    
    def calculate_original_price(self):
        """محاسبه مجموع قیمت کتاب‌های موجود در پکیج"""
        return sum(product.price for product in self.products.all())
    
    def save(self, *args, **kwargs):
        # محاسبه خودکار قیمت اصلی
        if self.pk:
            self.original_price = self.calculate_original_price()
        
        # اگر تخفیف درصدی تنظیم شده، قیمت را محاسبه کن
        if self.discount_percent > 0 and self.original_price:
            self.price = self.original_price * (1 - self.discount_percent / 100)
        elif not self.price and self.original_price:
            self.price = self.original_price
            
        super().save(*args, **kwargs)
    
    def get_products_count(self):
        """تعداد کتاب‌های موجود در پکیج"""
        return self.products.count()
    
    def get_savings(self):
        """میزان صرفه‌جویی"""
        if self.original_price and self.price:
            return self.original_price - self.price
        return 0