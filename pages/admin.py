from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import ValidationError
from .models import ContactInfo, CooperationInfo

@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    fieldsets = (
        ('main_info', {
            'fields': ('address', 'postal_code', 'phone')
        }),
        ('contacts', {
            'fields': ('whatsapp', 'email')
        }),
    )




@admin.register(CooperationInfo)
class CooperationInfoAdmin(admin.ModelAdmin):
    fieldsets = (
        ("contains", {
            'fields': (
                'intro_text',
                'invitation_text',
            )
        }),
    )

    def save_model(self, request, obj, form, change):
        """مدیریت ذخیره‌سازی با نمایش خطاهای اعتبارسنجی"""
        try:
            obj.full_clean()  # اعتبارسنجی قبل از ذخیره
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            messages.error(request, f"خطا: {', '.join(e.messages)}")
            # بازگشت به صفحه ویرایش با نمایش خطاها
            return

    def add_view(self, request, form_url='', extra_context=None):
        """افزودن پیام راهنما در صفحه افزودن"""
        if CooperationInfo.objects.exists():
            messages.warning(request, "در حال حاضر یک رکورد برای صفحه همکاری وجود دارد. برای افزودن رکورد جدید، ابتدا رکورد فعلی را حذف کنید.")
        return super().add_view(request, form_url, extra_context)

    
