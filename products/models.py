from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from ckeditor.fields import RichTextField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q, Avg, Sum, Value, F
from django.db.models.functions import Coalesce
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.core.cache import cache


class ProductManager(models.Manager):
    """Optimized manager for Product"""
    
    def get_active_products(self):
        """Get active products"""
        return self.filter(active=True)
    
    def get_on_sale_products(self):
        """Get on-sale products"""
        on_sale_condition = (
            Q(special_price__gt=0) |
            Q(discount_percent__gt=0)
        )
        return self.filter(active=True).filter(on_sale_condition)
    
    def with_ratings(self):
        """Annotate products with average rating"""
        return self.annotate(
            avg_rating_calc=Coalesce(
                Avg('comments__stars', filter=Q(comments__active=True)),
                Value(0.0)
            )
        )
    
    def with_sales_count(self):
        """Annotate products with total sales"""
        return self.annotate(
            total_sold_calc=Coalesce(
                Sum('order_items__quantity', filter=Q(order_items__order__is_paid=True)),
                Value(0)
            )
        )


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

    title = models.CharField(max_length=200, verbose_name=_('title'), db_index=True)
    category = models.CharField(
        max_length=50,
        choices=Category.choices,
        default=Category.OTHER,
        verbose_name=_('category'),
        db_index=True,
    )
    description = RichTextField(verbose_name=_('description'))
    price = models.PositiveIntegerField(default=0, verbose_name=_('price'), db_index=True)
    active = models.BooleanField(default=True, verbose_name=_('active'), db_index=True)
    image = models.ImageField(upload_to='product/product_cover/', blank=True, verbose_name=_('image'))
    
    author = models.CharField(max_length=200, blank=True, verbose_name=_('author'), db_index=True)
    publisher = models.CharField(max_length=200, blank=True, verbose_name=_('publisher'), db_index=True)
    isbn = models.CharField(max_length=30, blank=True, verbose_name=_('isbn'), db_index=True)
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
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_index=True,
    )
    discount_start_date = models.DateTimeField(_('discount start date'), null=True, blank=True)
    discount_end_date = models.DateTimeField(_('discount end date'), null=True, blank=True)
    special_price = models.PositiveIntegerField(_('special price'), default=0, validators=[MinValueValidator(0)], db_index=True)

    datetime_created = models.DateTimeField(default=timezone.now, verbose_name=_('created'), db_index=True)
    datetime_modified = models.DateTimeField(auto_now=True, verbose_name=_('modified'))

    objects = ProductManager()

    class Meta:
        verbose_name = _('product')
        verbose_name_plural = _('products')
        ordering = ['-datetime_created']
        indexes = [
            models.Index(fields=['category', 'active']),
            models.Index(fields=['author', 'active']),
            models.Index(fields=['discount_percent', 'special_price']),
        ]

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:product_detail', args=[self.pk])
    
    def is_on_sale(self):
        """Check if product is on sale"""
        if self.special_price > 0:
            return True
        if self.discount_percent > 0:
            return True
        return False
    
    def get_discounted_price(self):
        """Calculate discounted price"""
        if not self.is_on_sale():
            return self.price
        
        if self.special_price > 0:
            return min(self.special_price, self.price)
        
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
        """Check if product is new"""
        return (timezone.now() - self.datetime_created).days < 30
    
    @property
    def available_stock(self):
        """Get available stock"""
        return max(0, self.stock - self.reserved_stock)
    
    def get_avg_rating(self):
        """Get average rating with caching"""
        cache_key = f'product_avg_rating_{self.pk}'
        avg = cache.get(cache_key)
        if avg is None:
            avg = self.comments.filter(active=True).aggregate(
                avg=models.Avg('stars')
            )['avg'] or 0
            cache.set(cache_key, avg, 300)
        return avg
    
    def is_in_stock(self, quantity=1):
        """Check if product has enough stock"""
        return self.available_stock >= quantity
    
    def decrease_stock(self, quantity=1):
        """Decrease stock atomically"""
        updated = Product.objects.filter(
            pk=self.pk,
            stock__gte=quantity
        ).update(
            stock=F('stock') - quantity
        )
        if updated:
            self.refresh_from_db(fields=['stock'])
            return True
        return False
    
    def increase_stock(self, quantity=1):
        """Increase stock atomically"""
        Product.objects.filter(pk=self.pk).update(
            stock=F('stock') + quantity
        )
        self.refresh_from_db(fields=['stock'])
    
    def reserve_stock(self, quantity):
        """Reserve stock atomically"""
        updated = Product.objects.filter(
            pk=self.pk,
            stock__gte=F('reserved_stock') + quantity
        ).update(
            reserved_stock=F('reserved_stock') + quantity
        )
        if updated:
            self.refresh_from_db(fields=['reserved_stock'])
            return True
        return False
    
    def release_stock(self, quantity):
        """Release reserved stock"""
        Product.objects.filter(pk=self.pk).update(
            reserved_stock=F('reserved_stock') - quantity
        )
        self.refresh_from_db(fields=['reserved_stock'])


class ActiveCommentsManager(models.Manager):
    """Manager for active comments"""
    def get_queryset(self):
        return super().get_queryset().filter(active=True).select_related('author', 'product')


class Comment(models.Model):
    PRODUCT_STARS = [
        (1, _('Very Bad')),
        (2, _('Bad')), 
        (3, _('Normal')), 
        (4, _('Good')), 
        (5, _('Perfect')),  
    ]

    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='comments', 
        verbose_name=_('product'),
        db_index=True,
    )
    author = models.ForeignKey(
        get_user_model(), 
        on_delete=models.CASCADE, 
        related_name='comments', 
        verbose_name=_('author'),
        db_index=True,
    )
    body = models.TextField(verbose_name=_('comment text'))
    stars = models.IntegerField(choices=PRODUCT_STARS, verbose_name=_('rating'), db_index=True)
    datetime_created = models.DateTimeField(auto_now_add=True, db_index=True)
    datetime_modified = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True, verbose_name=_('active'), db_index=True)

    objects = models.Manager()
    active_comments_manager = ActiveCommentsManager()

    class Meta:
        verbose_name = _('comment')
        verbose_name_plural = _('comments')
        ordering = ['-datetime_created']
        indexes = [
            models.Index(fields=['product', 'active']),
            models.Index(fields=['author', 'active']),
        ]

    def get_absolute_url(self):
        return reverse('product:product_detail', args=[self.product.id])
    
    def __str__(self):
        return f'{self.author.username} - {self.product.title}'


class Package(models.Model):
    title = models.CharField(_('title'), max_length=200, db_index=True)
    slug = models.SlugField(_('slug'), max_length=200, unique=True, allow_unicode=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(_('image'), upload_to='packages/', blank=True, null=True)
    
    products = models.ManyToManyField(
        'Product',
        related_name='packages',
        verbose_name=_('products'),
        limit_choices_to={'active': True},
        blank=True,
    )
    
    original_price = models.PositiveIntegerField(default=0, verbose_name=_('original price'), validators=[MinValueValidator(0)])
    price = models.PositiveIntegerField(default=0, verbose_name=_('price'), validators=[MinValueValidator(0)], db_index=True)
    discount_percent = models.PositiveSmallIntegerField(_('discount percent'), default=0)
    manual_price = models.PositiveIntegerField(default=0, verbose_name=_('manual price'), validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(_('stock'), default=0, validators=[MinValueValidator(0)])
    active = models.BooleanField(_('active'), default=True, db_index=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True, db_index=True)
    datetime_modified = models.DateTimeField(_('modified'), auto_now=True)
    
    class Meta:
        verbose_name = _('package')
        verbose_name_plural = _('packages')
        ordering = ['-datetime_created']
        indexes = [
            models.Index(fields=['active', 'price']),
        ]
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:package_detail', args=[self.slug])
    
    def calculate_original_price(self):
        """Calculate sum of product prices"""
        return self.products.filter(active=True).aggregate(
            total=Sum('price')
        )['total'] or 0
    
    def get_products_count(self):
        """Get number of active products"""
        return self.products.filter(active=True).count()
    
    def get_total_weight(self):
        """Calculate total weight"""
        return self.products.filter(active=True).aggregate(
            total=Sum('weight')
        )['total'] or 0
    
    def calculate_savings(self):
        """Calculate savings"""
        if self.original_price > self.price:
            return self.original_price - self.price
        return 0
    
    def get_discount_percent_display(self):
        """Get discount percentage"""
        if self.original_price > 0 and self.price < self.original_price:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0
    
    def is_in_stock(self):
        """Check if package is in stock"""
        return self.stock > 0
    
    def decrease_stock(self, quantity=1):
        """Decrease stock atomically"""
        updated = Package.objects.filter(
            pk=self.pk,
            stock__gte=quantity
        ).update(
            stock=F('stock') - quantity
        )
        if updated:
            self.refresh_from_db(fields=['stock'])
            return True
        return False
    
    def _update_prices(self):
        """Calculate and update prices based on products"""
        if self.pk:
            self.original_price = self.calculate_original_price()
            
            if self.manual_price and self.manual_price > 0:
                self.price = self.manual_price
            elif self.discount_percent > 0 and self.original_price > 0:
                self.price = int(self.original_price * (1 - self.discount_percent / 100))
            else:
                self.price = self.original_price
            
            self.original_price = int(self.original_price)
            self.price = int(self.price)
            
            Package.objects.filter(pk=self.pk).update(
                original_price=self.original_price,
                price=self.price,
            )
    
    def save(self, *args, **kwargs):
        """Save package with price calculation"""
        if kwargs.get('force_insert', False):
            kwargs.pop('force_insert')
        
        if not self.pk:
            super().save(*args, **kwargs)
            self._update_prices()
        else:
            super().save(*args, **kwargs)


@receiver(m2m_changed, sender=Package.products.through)
def update_package_price_on_product_change(sender, instance, action, **kwargs):
    """Update package price when products change"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        if isinstance(instance, Package):
            instance._update_prices()


class DiscountCode(models.Model):
    code = models.CharField(_('code'), max_length=50, unique=True, db_index=True)
    percent = models.PositiveSmallIntegerField(_('percent'), default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    amount = models.PositiveIntegerField(_('amount'), default=0)
    max_uses = models.PositiveIntegerField(_('max uses'), default=1)
    used_count = models.PositiveIntegerField(_('used count'), default=0)
    active = models.BooleanField(_('active'), default=True, db_index=True)
    valid_from = models.DateTimeField(_('valid from'), null=True, blank=True)
    valid_until = models.DateTimeField(_('valid until'), null=True, blank=True)
    datetime_created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('discount code')
        verbose_name_plural = _('discount codes')
        ordering = ['-datetime_created']
    
    def __str__(self):
        return self.code
    
    def is_valid(self):
        """Check if discount code is valid"""
        if not self.active:
            return False
        if self.used_count >= self.max_uses:
            return False
        if self.valid_from and timezone.now() < self.valid_from:
            return False
        if self.valid_until and timezone.now() > self.valid_until:
            return False
        return True
    
    def apply_discount(self, total_price):
        """Apply discount to total price"""
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
    user = models.ForeignKey(
        get_user_model(), 
        on_delete=models.CASCADE, 
        related_name='tiered_discounts',
        db_index=True,
    )
    current_tier = models.PositiveSmallIntegerField(_('current tier'), default=0)
    datetime_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('tiered discount')
        verbose_name_plural = _('tiered discounts')
        unique_together = ['user']
    
    def __str__(self):
        return f'{self.user.username} - Tier {self.current_tier}'
    
    def get_discount_percent(self):
        """Get discount percentage for current tier"""
        tier_percents = {0: 0, 1: 10, 2: 20, 3: 50}
        return tier_percents.get(self.current_tier, 0)
    
    def advance_tier(self):
        """Advance to next tier"""
        if self.current_tier < 3:
            self.current_tier += 1
            self.save(update_fields=['current_tier', 'datetime_updated'])
            return True
        return False
    
    def reset(self):
        """Reset to tier 0"""
        self.current_tier = 0
        self.save(update_fields=['current_tier', 'datetime_updated'])


class ProductBlog(models.Model):
    class BlogType(models.TextChoices):
        ARTICLE = 'ARTICLE', _('Article')
        NEWS = 'NEWS', _('News')
        STORY = 'STORY', _('Story')
    
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='blogs', 
        verbose_name=_('product'),
        db_index=True,
    )
    title = models.CharField(_('title'), max_length=200, db_index=True)
    content = RichTextField(_('content'))
    blog_type = models.CharField(_('type'), max_length=20, choices=BlogType.choices, default=BlogType.ARTICLE, db_index=True)
    video = models.FileField(_('video'), upload_to='products/videos/', blank=True, null=True)
    author_name = models.CharField(_('author name'), max_length=200, blank=True)
    is_active = models.BooleanField(_('active'), default=True, db_index=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True, db_index=True)
    datetime_updated = models.DateTimeField(_('updated'), auto_now=True)
    
    class Meta:
        verbose_name = _('Product Blog')
        verbose_name_plural = _('Product Blogs')
        ordering = ['-datetime_created']
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['blog_type', 'is_active']),
        ]
    
    def __str__(self):
        return f'{self.product.title} - {self.title}'


class InstallmentPlan(models.Model):
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='installment_plans', 
        verbose_name=_('product'),
        db_index=True,
    )
    month_count = models.PositiveSmallIntegerField(_('month count'), default=3)
    prepayment_percent = models.PositiveSmallIntegerField(_('prepayment percent'), default=30)
    is_active = models.BooleanField(_('active'), default=True, db_index=True)
    
    class Meta:
        verbose_name = _('Installment Plan')
        verbose_name_plural = _('Installment Plans')
        indexes = [
            models.Index(fields=['product', 'is_active']),
        ]
    
    def __str__(self):
        return f'{self.product.title} - {self.month_count} {_("months")}'
    
    def calculate_monthly_payment(self):
        """Calculate monthly payment"""
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
    """FAQ for chat bot"""
    
    question = models.CharField(_('question'), max_length=300, db_index=True)
    answer = models.TextField(_('answer'))
    
    related_questions = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='related_to',
        verbose_name=_('related questions'),
        help_text=_('Questions to suggest after this answer'),
    )
    
    order = models.PositiveIntegerField(_('display order'), default=0, db_index=True)
    is_active = models.BooleanField(_('active'), default=True, db_index=True)
    datetime_created = models.DateTimeField(_('created'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')
        ordering = ['order', '-datetime_created']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]
    
    def __str__(self):
        return self.question