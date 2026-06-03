from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_("user_order"), on_delete=models.CASCADE)
    is_paid = models.BooleanField(default= False)

    first_name = models.CharField(max_length= 100)
    last_name = models.CharField(max_length= 100)
    phone_number = PhoneNumberField(verbose_name =_('phone_number'))
    # phone_number = models.CharField(max_length  = 15)
    address = models.CharField(max_length= 700)
    order_notes = models.CharField(_("note"), max_length=700 , blank = True)

    datetime_created = models.DateTimeField(auto_now_add= True, verbose_name =_('Date Time of Creation'))
    datetime_modified = models.DateTimeField(auto_now= True , verbose_name =_('Date Time of Modified'))


    def __str__(self):
        return f'Order{self.id}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order , on_delete= models.CASCADE , related_name='items')
    product = models.ForeignKey('products.Product' , on_delete= models.CASCADE , related_name='order_items')
    quantity = models.PositiveBigIntegerField(default=1)
    price = models.PositiveIntegerField(verbose_name=_('Product Price'))


def __str__(self):
    return f'OrderItem {self.id}: {self.product} * {self.quantity} (price :{self.price})'

