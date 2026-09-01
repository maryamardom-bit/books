from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from ckeditor.fields import RichTextField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q
from django.db.models.signals import m2m_changed
from django.dispatch import receiver


class ProductManager(models.Manager):
    def get_active_products(self):
        return self.filter(active=True)
    
    def get_on_sale_products(self):
        current_time = timezone.now()
        on_sale_condition = (
            Q(special_price__gt=0) |
            Q(discount_percent__gt=0)
        )
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
        RAGHIEI = 'raghiei', _('Raghei')
        VAZEHI = 'vazehi', _('Vazehi')
        JEYBI = 'jeybi', _('Jeybi')
        RAHLEI = 'rahlei', _('Rahlei')
        OTHER = 'other', _('Other')
   
    class CoverType(models.TextChoices):
        SHOMIZ = 'shomiz', _('Shomiz')
        GARD = 'gard', _('Gard')
        OTHER = 'other', _('Other')

    title = models.CharField(max_length=200, verbose_name=_('title'))
    category = models.CharField(
        max_length=50,
        choices=Category.choices,
        default=Category.OTHER,
        verbose_name=_('category')
    )
    description = RichTextField(verbose_name=_('description'))
    price = models.PositiveIntegerField(default=0, verbose_name=_('price'))
    active = models.BooleanField(default=True, verbose_name=_('active'))
    image = models.ImageField(upload_to='product/product_cover/', blank=True, verbose_name=_('image'))
    
    author = models.CharField(max_length=200, blank=True, verbose_name=_('author'))
    publisher = models.CharField(max_length=200, blank=True, verbose_name=_('publisher'))
    isbn = models.CharField(max_length=30, blank=True, verbose_name=_('isbn'))
    year_of_publication = models.IntegerField(null=True, blank=True, verbose_name=_('year of publication'))
    edition = models.CharField(max_length=100, blank=True, verbose_name=_('edition'))
    number_of_pages = models.IntegerField(null=True, blank=True, verbose_name=_('number of pages'))
    book_size = models.CharField(max_length=30, choices=BookSize.choices, blank=True, null=True, verbose_name=_('book size'))
    cover_type = models.CharField(max_length=30, choices=CoverType.choices, blank=True, null=True, verbose_name=_('cover type'))
    publication_date = models.IntegerField(null=True, blank=True, verbose_name=_('publication date'))
    printing_series = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('printing series'))
    weight = models.IntegerField(null=True, blank=True, verbose_name=_('weight'))
    stock = models.PositiveIntegerField(default=0, verbose_name=_('stock'), validators=[MinValueValidator(0)])
    reserved_stock = models.PositiveIntegerField(default=0, verbose_name=_('reserved stock'), validators=[MinValueValidator(0)])

    discount_percent = models.PositiveSmallIntegerField(
        _('discount percent'),
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    discount_start_date = models.DateTimeField(_('discount start date'), null=True, blank=True)
    discount_end_date = models.DateTimeField(_('discount end date'), null=True, blank=True)
    special_price = models.PositiveIntegerField(_('special price'), default=0, validators=[MinValueValidator(0)])

    datetime_created = models.DateTimeField(default=timezone.now, verbose_name=_('created'))
    datetime_modified = models.DateTimeField(auto_now=True, verbose_name=_('modified'))

    objects = ProductManager()

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:product_detail', args=[self.pk])
    
    def is_on_sale(self):
        """Check if product is on sale - simple version without date check"""
        # اگه قیمت ویژه داره
        if self.special_price > 0:
            return True
        
        # اگه درصد تخفیف داره
        if self.discount_percent > 0:
            return True
        
        return False
    
    def get_discounted_price(self):
        """Calculate discounted price"""
        if not self.is_on_sale():
            return self.price
        
        # اولویت با قیمت ویژه
        if self.special_price > 0:
            return min(self.special_price, self.price)
        
        # تخفیف درصدی
        if self.discount_percent > 0:
            discounted = self.price * (1 - self.discount_percent / 100)
            return max(int(discounted), 0)
        
        return self.price
    
    def get_savings(self):
        """Calculate savings"""
        if self.is_on_sale():
            return self.price - self.get_discounted_price()
        return 0
    
    def get_discount_percent_display(self):
        """Get actual discount percentage"""
        if self.is_on_sale() and self.price > 0:
            discounted_price = self.get_discounted_price()
            return int(((self.price - discounted_price) / self.price) * 100)
        return 0
    
    @property
    def is_new(self):
        return (timezone.now() - self.datetime_created).days < 30
    
    @property
    def available_stock(self):
        return max(0, self.stock - self.reserved_stock)
    
    @property
    def avg_rating(self):
        comments = self.comments.filter(active=True)
        if comments.exists():
            return comments.aggregate(models.Avg('stars'))['stars__avg']
        return 0
    
    def is_in_stock(self, quantity=1):
        return self.available_stock >= quantity
    
    def decrease_stock(self, quantity=1):
        if self.is_in_stock(quantity):
            self.stock -= quantity
            self.save(update_fields=['stock'])
            return True
        return False
    
    def increase_stock(self, quantity=1):
        self.stock += quantity
        self.save(update_fields=['stock'])
    
    def reserve_stock(self, quantity):
        if self.available_stock >= quantity:
            self.reserved_stock += quantity
            self.save(update_fields=['reserved_stock'])
            return True
        return False
    
    def release_stock(self, quantity):
        self.reserved_stock = max(0, self.reserved_stock - quantity)
        self.save(update_fields=['reserved_stock'])


class ActiveCommentsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(active=True)


class Comment(models.Model):
    PRODUCT_STARS = [
        (1, _('Very Bad')),
        (2, _('Bad')), 
        (3, _('Normal')), 
        (4, _('Good')), 
        (5, _('Perfect')),  
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments', verbose_name=_('product'))
    author = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='comments', verbose_name=_('author'))
    body = models.TextField(verbose_name=_('comment text'))
    stars = models.IntegerField(choices=PRODUCT_STARS, verbose_name=_('rating'))
    datetime_created = models.DateTimeField(auto_now_add=True)
    detetime_modified = models.DateTimeField(auto_now=True)  # ← این اسم در دیتابیس هست
    active = models.BooleanField(default=True, verbose_name=_('active'))

    objects = models.Manager()
    active_comments_manager = ActiveCommentsManager()

    def get_absolute_url(self):
        return reverse('product:product_detail', args=[self.product.id])
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

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
    
    original_price = models.PositiveIntegerField(default=0, verbose_name=_('original price'), validators=[MinValueValidator(0)])
    price = models.PositiveIntegerField(default=0, verbose_name=_('price'), validators=[MinValueValidator(0)])
    discount_percent = models.PositiveSmallIntegerField(_('discount percent'), default=0)
    manual_price = models.PositiveIntegerField(default=0, verbose_name=_('manual price'), validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(_('stock'), default=0, validators=[MinValueValidator(0)])
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
        return sum(product.price for product in self.products.filter(active=True))
    
    def get_products_count(self):
        return self.products.filter(active=True).count()
    
    def get_total_weight(self):
        return sum(product.weight or 0 for product in self.products.filter(active=True))
    
    def calculate_savings(self):
        if self.original_price > self.price:
            return self.original_price - self.price
        return 0
    
    def get_discount_percent_display(self):
        if self.original_price > 0 and self.price < self.original_price:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0
    
    def is_in_stock(self):
        return self.stock > 0
    
    def decrease_stock(self, quantity=1):
        if self.is_in_stock():
            self.stock -= quantity
            self.save(update_fields=['stock'])
            return True
        return False
    
    def _update_prices(self):
        """Calculate and update prices based on products"""
        if self.pk:  # فقط وقتی id داریم
            self.original_price = self.calculate_original_price()
            
            if self.manual_price and self.manual_price > 0:
                self.price = self.manual_price
            elif self.discount_percent > 0 and self.original_price > 0:
                self.price = int(self.original_price * (1 - self.discount_percent / 100))
            else:
                self.price = self.original_price
            
            self.original_price = int(self.original_price)
            self.price = int(self.price)
            
            # فقط فیلدهای قیمت را به‌روزرسانی کن
            super().save(update_fields=['original_price', 'price'])
    
    def save(self, *args, **kwargs):
        """
        Save package with price calculation.
        First save to get pk, then calculate prices based on M2M products.
        """
        # اگر force_insert داریم، حذفش کن
        if kwargs.get('force_insert', False):
            kwargs.pop('force_insert')
        
        # ذخیره اولیه برای گرفتن pk
        if not self.pk:
            super().save(*args, **kwargs)
            # بعد از گرفتن pk، قیمت‌ها را محاسبه کن
            self._update_prices()
        else:
            # اگر pk داریم، فقط ذخیره کن
            super().save(*args, **kwargs)


def _update_prices(self):
    """Calculate and update prices based on products"""
    if self.pk:  # فقط وقتی id داریم
        self.original_price = self.calculate_original_price()
        
        if self.manual_price and self.manual_price > 0:
            self.price = self.manual_price
        elif self.discount_percent > 0 and self.original_price > 0:
            self.price = int(self.original_price * (1 - self.discount_percent / 100))
        else:
            self.price = self.original_price
        
        self.original_price = int(self.original_price)
        self.price = int(self.price)
        
        # فقط فیلدهای قیمت را به‌روزرسانی کن
        super().save(update_fields=['original_price', 'price'])
    
@receiver(m2m_changed, sender=Package.products.through)
def update_package_price_on_product_change(sender, instance, action, **kwargs):
    if action in ['post_add', 'post_remove', 'post_clear']:
        if isinstance(instance, Package):
            instance.save()


class DiscountCode(models.Model):
    code = models.CharField(_('code'), max_length=50, unique=True)
    percent = models.PositiveSmallIntegerField(_('percent'), default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    amount = models.PositiveIntegerField(_('amount'), default=0)
    max_uses = models.PositiveIntegerField(_('max uses'), default=1)
    used_count = models.PositiveIntegerField(_('used count'), default=0)
    active = models.BooleanField(_('active'), default=True)
    valid_from = models.DateTimeField(_('valid from'), null=True, blank=True)
    valid_until = models.DateTimeField(_('valid until'), null=True, blank=True)
    datetime_created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.code
    
    def is_valid(self):
        if not self.active:
            return False
        if self.used_count >= self.max_uses:
            return False
        return True
    
    def apply_discount(self, total_price):
        if not self.is_valid():
            return total_price, 0
        if self.amount > 0:
            discount = min(self.amount, total_price)
        elif self.percent > 0:
            discount = int(total_price * self.percent / 100)
        else:
            discount = 0
        final_price = total_price - discount
        return final_price, discount


class TieredDiscount(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='tiered_discounts')
    current_tier = models.PositiveSmallIntegerField(_('current tier'), default=0)
    datetime_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f'{self.user.username} - Tier {self.current_tier}'
    
    def get_discount_percent(self):
        tier_percents = {0: 0, 1: 10, 2: 20, 3: 50}
        return tier_percents.get(self.current_tier, 0)
    
    def advance_tier(self):
        if self.current_tier < 3:
            self.current_tier += 1
            self.save(update_fields=['current_tier'])
            return True
        return False
    
    def reset(self):
        self.current_tier = 0
        self.save(update_fields=['current_tier'])


class ProductBlog(models.Model):
    class BlogType(models.TextChoices):
        ARTICLE = 'ARTICLE', _('Article')
        NEWS = 'NEWS', _('News')
        STORY = 'STORY', _('Story')
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='blogs', verbose_name=_('product'))
    title = models.CharField(_('title'), max_length=200)
    content = RichTextField(_('content'))
    blog_type = models.CharField(_('type'), max_length=20, choices=BlogType.choices, default=BlogType.ARTICLE)
    video = models.FileField(_('video'), upload_to='products/videos/', blank=True, null=True)
    author_name = models.CharField(_('author name'), max_length=200, blank=True)
    is_active = models.BooleanField(_('active'), default=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    datetime_updated = models.DateTimeField(_('updated'), auto_now=True)
    
    class Meta:
        verbose_name = _('Product Blog')
        verbose_name_plural = _('Product Blogs')
        ordering = ['-datetime_created']
    
    def __str__(self):
        return f'{self.product.title} - {self.title}'


class InstallmentPlan(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='installment_plans', verbose_name=_('product'))
    month_count = models.PositiveSmallIntegerField(_('month count'), default=3)
    prepayment_percent = models.PositiveSmallIntegerField(_('prepayment percent'), default=30)
    is_active = models.BooleanField(_('active'), default=True)
    
    class Meta:
        verbose_name = _('Installment Plan')
        verbose_name_plural = _('Installment Plans')
    
    def __str__(self):
        return f'{self.product.title} - {self.month_count} {_("months")}'
    
    def calculate_monthly_payment(self):
        product_price = self.product.get_discounted_price()
        prepayment = int(product_price * self.prepayment_percent / 100)
        remaining = product_price - prepayment
        monthly = remaining // self.month_count
        return {
            'prepayment': prepayment,
            'remaining': remaining,
            'monthly': monthly,
        }


class FAQ(models.Model):
    """سوالات متداول برای ربات چت"""
    
    question = models.CharField(_('question'), max_length=300)
    answer = models.TextField(_('answer'))
    
    # سوالات بعدی مرتبط
    related_questions = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='related_to',
        verbose_name=_('related questions'),
        help_text=_('Questions to suggest after this answer'),
    )
    
    order = models.PositiveIntegerField(_('display order'), default=0)
    is_active = models.BooleanField(_('active'), default=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')
        ordering = ['order', '-datetime_created']
    
    def __str__(self):
        return self.question