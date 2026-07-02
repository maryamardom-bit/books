from django.db import models

class ContactInfo(models.Model):
    address = models.TextField(verbose_name="address")
    postal_code = models.CharField(max_length=20, verbose_name="postal_cart ")
    phone = models.CharField(max_length=20, verbose_name="phone")
    whatsapp = models.CharField(max_length=20, verbose_name="whatsapp")
    email = models.EmailField(verbose_name="email")
    
    class Meta:
        verbose_name = " contact_info"
        verbose_name_plural = "contact_info"
    
    def str(self):
        return " contavt_info"
