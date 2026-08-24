from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.db import models as django_models
from jalali_date.admin import ModelAdminJalaliMixin
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime
import jdatetime

from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(CustomUser)
class CustomUserAdmin(ModelAdminJalaliMixin, UserAdmin):
    model = CustomUser
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    
    list_display = ('username', 'email', 'phone_number', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'is_superuser')
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    ordering = ('username',)
    
    fieldsets = UserAdmin.fieldsets + (
        (_('Additional Info'), {'fields': ('phone_number', 'wallet_balance', 'birth_date', 'address', 'postal_code')}),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Additional Info'), {'fields': ('phone_number',)}),
    )
    
    formfield_overrides = {
        django_models.DateField: {'widget': AdminJalaliDateWidget},
        django_models.DateTimeField: {'widget': AdminSplitJalaliDateTime},
    }
    
    readonly_fields = ('last_login', 'date_joined')  # فقط نمایش
    
    def last_login_jalali(self, obj):
        """نمایش شمسی آخرین ورود"""
        if obj.last_login:
            jalali_date = jdatetime.datetime.fromgregorian(datetime=obj.last_login)
            return jalali_date.strftime('%Y/%m/%d %H:%M')
        return '-'
    last_login_jalali.short_description = 'آخرین ورود'
    
    def date_joined_jalali(self, obj):
        """نمایش شمسی تاریخ پیوستن"""
        if obj.date_joined:
            jalali_date = jdatetime.datetime.fromgregorian(datetime=obj.date_joined)
            return jalali_date.strftime('%Y/%m/%d %H:%M')
        return '-'
    date_joined_jalali.short_description = 'تاریخ پیوستن'