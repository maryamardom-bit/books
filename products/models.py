from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from ckeditor.fields import RichTextField


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
    
