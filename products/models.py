from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from ckeditor.fields import RichTextField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q


class ProductManager(models.Manager):
    """مدیریت کوئری‌های مربوط به محصولات"""
    
    def get_active_products(self):
        """دریافت محصولات فعال"""
        return self.filter(active=True)
    
    def get_on_sale_products(self):
        """دریافت محصولات دارای تخفیف با کوئری بهینه"""
        current_time = timezone.now()
        
        # شرایط تخفیف با استفاده از Q objects
        on_sale_condition = (
            Q(special_price__gt=0) |
            (
                Q(discount_percent__gt=0) &
                (
                    Q(discount_start_date__isnull=True) |
                    Q(discount_start_date__lte=current_time)
                ) &
                (
                    Q(discount_end_date__isnull=True) |
                    Q(discount_end_date__gte=current_time)
                )
            )
        )
        
        # اعمال فیلتر
        return self.filter(active=True).filter(on_sale_condition)


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

    # ==========================================
    # فیلدهای اصلی
    # ==========================================
    title = models.CharField(max_length=100, verbose_name=_('product_title'))
    category = models.CharField(
        max_length=50,  # تغییر از 20 به 50 برای پشتیبانی از مقادیر طولانی‌تر
        choices=Category.choices,
        default=Category.OTHER,
        verbose_name=_('product_category')
    )
    description = RichTextField(verbose_name=_('description'))
    price = models.PositiveIntegerField(default=0, verbose_name=_('price'))
    active = models.BooleanField(default=True, verbose_name=_('active'))
    image = models.ImageField(upload_to='product/product_cover/', blank=True, verbose_name=_('image'))
    
    # ==========================================
    # فیلدهای اطلاعات کتاب
    # ==========================================
    author = models.CharField(max_length=200, blank=True, verbose_name=_('author'))
    publisher = models.CharField(max_length=200, blank=True, verbose_name=_('publisher'))
    isbn = models.CharField(max_length=20, blank=True, verbose_name=_('isbn'))
    year_of_publication = models.IntegerField(null=True, blank=True, verbose_name=_('year_of_publication'))
    edition = models.CharField(max_length=50, blank=True, verbose_name=_('edition'))
    number_of_pages = models.IntegerField(null=True, blank=True, verbose_name=_('number_of_pages'))
    book_size = models.CharField(max_length=20, choices=BookSize.choices, blank=True, null=True, verbose_name=_('book_size'))
    cover_type = models.CharField(max_length=20, choices=CoverType.choices, blank=True, null=True, verbose_name=_('cover_type'))
    publication_date = models.IntegerField(null=True, blank=True, verbose_name=_('publication_date'))
    printing_series = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('printing_series'))
    weight = models.IntegerField(null=True, blank=True, verbose_name=_('weight'))

    # ==========================================
    # فیلدهای تخفیف
    # ==========================================
    discount_percent = models.PositiveSmallIntegerField(
        _('discount percent'),
        default=0,
        help_text=_('درصد تخفیف (0 تا 100)'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    discount_start_date = models.DateTimeField(
        _('discount start date'),
        null=True,
        blank=True,
        help_text=_('زمان شروع تخفیف')
    )
    
    discount_end_date = models.DateTimeField(
        _('discount end date'),
        null=True,
        blank=True,
        help_text=_('زمان پایان تخفیف')
    )
    
    special_price = models.PositiveIntegerField(
        _('special price'),
        default=0,
        help_text=_('قیمت ویژه (اگر وارد شود، تخفیف به صورت مبلغ ثابت اعمال می‌شود)'),
        validators=[MinValueValidator(0)]
    )

    # ==========================================
    # فیلدهای زمانی
    # ==========================================
    datetime_created = models.DateTimeField(default=timezone.now, verbose_name=_('datetime_created'))
    datetime_modified = models.DateTimeField(auto_now=True, verbose_name=_('datetime_modified'))

    # ==========================================
    # مدل‌منیجر
    # ==========================================
    objects = ProductManager()

    # ==========================================
    # متدهای اصلی
    # ==========================================
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:product_detail', args=[self.pk])
    
    def is_on_sale(self):
        """بررسی اینکه محصول در حال تخفیف است یا نه"""
        current_time = timezone.now()
        
        # اگر قیمت ویژه وارد شده باشد
        if self.special_price > 0:
            return True
        
        # بررسی تخفیف درصدی با زمان‌بندی
        if self.discount_percent > 0:
            # اگر تاریخ شروع و پایان تعیین نشده، تخفیف همیشه فعال است
            if not self.discount_start_date and not self.discount_end_date:
                return True
            
            # اگر تاریخ شروع تعیین شده و هنوز شروع نشده
            if self.discount_start_date and current_time < self.discount_start_date:
                return False
            
            # اگر تاریخ پایان تعیین شده و گذشته
            if self.discount_end_date and current_time > self.discount_end_date:
                return False
            
            # در غیر این صورت تخفیف فعال است
            return True
        
        return False
    
    def get_discounted_price(self):
        """محاسبه قیمت با تخفیف"""
        if not self.is_on_sale():
            return self.price
        
        # اگر قیمت ویژه وارد شده باشد
        if self.special_price > 0:
            return min(self.special_price, self.price)
        
        # تخفیف درصدی
        if self.discount_percent > 0:
            discounted = self.price * (1 - self.discount_percent / 100)
            return max(int(discounted), 0)
        
        return self.price
    
    def get_savings(self):
        """میزان صرفه‌جویی"""
        if self.is_on_sale():
            return self.price - self.get_discounted_price()
        return 0
    
    def get_discount_percent_display(self):
        """درصد تخفیف واقعی"""
        if self.is_on_sale() and self.price > 0:
            discounted_price = self.get_discounted_price()
            return int(((self.price - discounted_price) / self.price) * 100)
        return 0
    
    @property
    def is_new(self):
        """آیا محصول جدید است (کمتر از 30 روز)"""
        return (timezone.now() - self.datetime_created).days < 30


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
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=200, unique=True, allow_unicode=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(_('image'), upload_to='packages/', blank=True, null=True)
    
    products = models.ManyToManyField(
        'Product',
        related_name='packages',
        verbose_name=_('products'),
        limit_choices_to={'active': True},
        blank=True
    )
    
    original_price = models.PositiveIntegerField(
        default=0, 
        verbose_name=_('original price'),
        validators=[MinValueValidator(0)]
    )
    
    price = models.PositiveIntegerField(
        default=0, 
        verbose_name=_('price'),
        validators=[MinValueValidator(0)]
    )
    
    discount_percent = models.PositiveSmallIntegerField(
        _('discount percent'),
        default=0,
        help_text=_('Discount percentage (if set, price will be auto-calculated)')
    )
    
    manual_price = models.PositiveIntegerField(
        default=0, 
        verbose_name=_('manual price'),
        validators=[MinValueValidator(0)]
    )
    
    stock = models.PositiveIntegerField(
        _('stock'),
        default=0,
        help_text=_('Available stock for this package'),
        validators=[MinValueValidator(0)]
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
        return sum(product.price for product in self.products.filter(active=True))
    
    def get_products_count(self):
        """تعداد کتاب‌های موجود در پکیج"""
        return self.products.filter(active=True).count()
    
    def calculate_savings(self):
        """میزان صرفه‌جویی به صورت عدد صحیح"""
        if self.original_price > self.price:
            return self.original_price - self.price
        return 0
    
    def get_discount_percent_display(self):
        """درصد تخفیف واقعی را محاسبه می‌کند"""
        if self.original_price > 0 and self.price < self.original_price:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0
    
    def is_in_stock(self):
        """بررسی موجودی"""
        return self.stock > 0
    
    def save(self, *args, **kwargs):
        # اگر شیء جدید است، ابتدا ذخیره کن
        if not self.pk:
            super().save(*args, **kwargs)
        
        # محاسبه قیمت اصلی
        self.original_price = self.calculate_original_price()
        
        # تعیین قیمت نهایی
        if self.manual_price and self.manual_price > 0:
            self.price = self.manual_price
        elif self.discount_percent > 0 and self.original_price > 0:
            self.price = int(self.original_price * (1 - self.discount_percent / 100))
        else:
            self.price = self.original_price
        
        # تبدیل به عدد صحیح
        self.original_price = int(self.original_price)
        self.price = int(self.price)
        
        super().save(*args, **kwargs)