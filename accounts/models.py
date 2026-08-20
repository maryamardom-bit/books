from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


class CustomUser(AbstractUser):
    """
    کاربر سفارشی با فیلدهای اضافه برای فروشگاه کتاب
    """
    phone_number = PhoneNumberField(
        _('phone number'),
        blank=True,
        null=True,
        help_text=_('شماره موبایل برای ارسال پیامک تخفیف')
    )
    
    wallet_balance = models.PositiveIntegerField(
        _('wallet balance'),
        default=0,
        help_text=_('موجودی کیف پول (تومان)')
    )
    
    birth_date = models.DateField(
        _('birth date'),
        null=True,
        blank=True,
        help_text=_('تاریخ تولد برای پیامک تبریک')
    )
    
    address = models.TextField(
        _('address'),
        blank=True,
        help_text=_('آدرس پستی')
    )
    
    postal_code = models.CharField(
        _('postal code'),
        max_length=20,
        blank=True,
        help_text=_('کد پستی')
    )
    
    def __str__(self):
        return self.username or self.email

    def get_full_name(self):
        """نام کامل کاربر"""
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'
        return self.username or self.email