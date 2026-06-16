from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,verbose_name=_('user'))
    is_paid = models.BooleanField(_('is_paid?') ,default= False)

    first_name = models.CharField(_('first_name'),max_length= 100,)
    last_name = models.CharField(_('last_name'),max_length= 100,)
    phone_number = models.CharField(_('phone_number') , max_length= 15)
    # phone_number = models.CharField(max_length  = 15)
    address = models.CharField(_('address'),max_length= 700,)
    order_notes = models.CharField(_("note"), max_length=700 , blank = True)

    datetime_created = models.DateTimeField(_('Date Time of Creation'),auto_now_add= True, )
    datetime_modified = models.DateTimeField(_('Date Time of Modified'),auto_now= True ,)


    def __str__(self):
        return f'Order{self.id}'

    def get_total_price(self):
        return sum(item.quantity * item.price for item in self.item.all())
    
        # result= 0
        # for item in self.items.all():
        #     result += item.price * item.quantity
        # return result

class OrderItem(models.Model):
    order = models.ForeignKey(Order , on_delete= models.CASCADE , related_name='items')
    product = models.ForeignKey('products.Product' , on_delete= models.CASCADE , related_name='order_items')
    quantity = models.PositiveBigIntegerField(default=1)
    price = models.PositiveIntegerField(verbose_name=_('Product Price'))


def __str__(self):
    return f'OrderItem {self.id}: {self.product} * {self.quantity} (price :{self.price})'

