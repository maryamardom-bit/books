from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


class CustomUser(AbstractUser):
    phone_number = PhoneNumberField(
        _('phone number'),
        blank=True,
        null=True,
    )
    wallet_balance = models.PositiveIntegerField(_('wallet balance'), default=0)
    birth_date = models.CharField(
        _('birth date'),
        max_length=10,
        blank=True,
        help_text=_('Format: 1370/05/15'),
    )
    address = models.TextField(_('address'), blank=True)
    postal_code = models.CharField(_('postal code'), max_length=20, blank=True)

    def __str__(self):
        return self.username or self.email

    def get_full_name(self):
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'
        return self.username or self.email

    def get_tiered_discount(self):
        from products.models import TieredDiscount
        tiered, _ = TieredDiscount.objects.get_or_create(user=self)
        return tiered