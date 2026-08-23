from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


class CustomUser(AbstractUser):
    """
    Custom user with additional fields for bookstore
    """
    phone_number = PhoneNumberField(
        _('phone number'),
        blank=True,
        null=True,
        help_text=_('mobile number for discount SMS')
    )
    
    wallet_balance = models.PositiveIntegerField(
        _('wallet balance'),
        default=0,
        help_text=_('wallet balance in Toman')
    )
    
    birth_date = models.DateField(
        _('birth date'),
        null=True,
        blank=True,
        help_text=_('birth date for birthday SMS')
    )
    
    address = models.TextField(
        _('address'),
        blank=True,
        help_text=_('postal address')
    )
    
    postal_code = models.CharField(
        _('postal code'),
        max_length=20,
        blank=True,
        help_text=_('postal code')
    )
    
    def __str__(self):
        return self.username or self.email

    def get_full_name(self):
        """Get full name of user"""
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'
        return self.username or self.email
    
    def get_tiered_discount(self):
        """Get tiered discount for user"""
        from products.models import TieredDiscount
        tiered, created = TieredDiscount.objects.get_or_create(user=self)
        return tiered