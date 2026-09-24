from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from ckeditor.fields import RichTextField

class ContactInfo(models.Model):
    address = models.TextField(verbose_name=_("address"))
    postal_code = models.CharField(max_length=20, verbose_name=_("postal cart"))
    phone = models.CharField(max_length=20, verbose_name=_("phone"))
    whatsapp = models.CharField(max_length=50, verbose_name=_("whatsapp"),null= True)
    email = models.EmailField(verbose_name=_("email"))
    
    class Meta:
        verbose_name = _("contact_info")
        verbose_name_plural = _("contact_infos")
    
    def __str__(self):
        return "contact_info"


class CooperationInfo(models.Model):
    intro_text = RichTextField(verbose_name=_("intro_text"))
    invitation_text = RichTextField(verbose_name=_("invitation_text"))
    is_active = models.BooleanField(default=True, verbose_name=_("active"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("last updated"))

    class Meta:
        verbose_name = _("cooperation")
        verbose_name_plural = _("cooperations")

    def __str__(self):
        return "cooperation_info"

    def clean(self):
        if not self.pk and CooperationInfo.objects.exists():
            raise ValidationError(_("Only one cooperation record can exist."))

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)



class AboutUs(models.Model):
    text = RichTextField(verbose_name=_("text"))
    is_active = models.BooleanField(default=True, verbose_name=_("active"))  
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("last updated")) 

    class Meta:
        verbose_name = _("about_us")
        verbose_name_plural = _("about_us_plural")  

    def __str__(self):
        return "about_us"
    
    def clean(self):
        if not self.pk and AboutUs.objects.exists():
            raise ValidationError(_("Only one about us record can exist."))

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class OrderCondition(models.Model):
    text = RichTextField(verbose_name=_("text"))
    is_active = models.BooleanField(default=True, verbose_name=_("active"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))

    class Meta:
        verbose_name = _("orderus")
        verbose_name_plural = _("orderus")

    def __str__(self):
        return "orderus"

    def clean(self):
        if not self.pk and OrderCondition.objects.exists():
            raise ValidationError(_("Only one orderus record can exist."))

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class SitePage(models.Model):
    class Source(models.TextChoices):
        PAGE = 'page', _('WordPress page')
        POST = 'post', _('WordPress post')

    wordpress_id = models.PositiveIntegerField(unique=True, db_index=True)
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=250, unique=True, allow_unicode=True)
    content = RichTextField(blank=True)
    excerpt = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.PAGE)
    status = models.CharField(max_length=20, default='publish')
    is_active = models.BooleanField(default=True)
    datetime_created = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('archived page')
        verbose_name_plural = _('archived pages')
        ordering = ['title']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('page:site_page', args=[self.slug])
 
