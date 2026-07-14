from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from ckeditor.fields import RichTextField



class Product(models.Model):

    class Category(models.TextChoices):
        HISTORY = 'history', _('history')
        DESIGN_THEORY = 'design_theory', _('design_theory')
        SUSTAINABLE = 'sustainable', _('sustainable')
        URBAN_PLANNING = 'urban_planning', _('urban_planning')
        MISC = 'misc', _('misc')

    title = models.CharField(max_length=100, verbose_name=_('Product Title'))
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.MISC,
        verbose_name=_('Product Category')
    )
    title = models.CharField(max_length=100, verbose_name=_('Product Title'))
    description = RichTextField(verbose_name=_('Product Discription'))
    short_discription = RichTextField(blank=True, verbose_name=_('Product Short_Discription'))
    price = models.PositiveIntegerField(default=0, verbose_name=_('Product Price'))
    active = models.BooleanField(default=True, verbose_name=_('Product Active'))
    image = models.ImageField(upload_to='product/product_cover/', blank=True, verbose_name=_('Product Image'))
    
    datetime_created = models.DateTimeField(default=timezone.now, verbose_name=_('Date Time of Creation'))
    datetime_modified = models.DateTimeField(auto_now=True, verbose_name=_('Date Time of Modified'))

    def str(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('product:product_detail', args=[self.pk])


class ActiveCommentsManager(models.Manager):
    def get_queryset(self):
        return super(ActiveCommentsManager, self).get_queryset().filter(active=True)


class Comment(models.Model):
    PRODUCT_STARS = [
        (1, _('Very Bad')),
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
    
    body = models.TextField(verbose_name=_('Comment Text'))
    stars = models.IntegerField(choices=PRODUCT_STARS, verbose_name=_('What is your score?'))

    datetime_created = models.DateTimeField(auto_now_add=True)
    detetime_modified = models.DateTimeField(auto_now=True)

    active = models.BooleanField(default=True, verbose_name=_('Comment_Active'))

    # manager
    objects = models.Manager()
    active_comments_manager = ActiveCommentsManager()

    def get_absolute_url(self):
        return reverse('product_detail', args=[self.product.id])
    