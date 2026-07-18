from django.contrib import admin,messages
from django.shortcuts import redirect
from django.core.exceptions import ValidationError
from .models import ContactInfo, CooperationInfo,AboutUs,OrderCondition

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
            messages.warning(request, "There is some record now.if you want to change please deleted old record.then try again")
        return super().add_view(request, form_url, extra_context)


@admin.register(AboutUs)
class AboutUsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("contains", {
            'fields': (
                'text',
                'is_active', 
                'updated_at',  
            )
        }),
    )
    readonly_fields = ('updated_at',)  

    def save_model(self, request, obj, form, change):
        try:
            obj.full_clean()
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            messages.error(request, f"eror: {', '.join(e.messages)}")
            return

    def add_view(self, request, form_url='', extra_context=None):
        if AboutUs.objects.exists():
            messages.warning(request, "There is some record now.if you want to change please deleted old record.then try again")
        return super().add_view(request, form_url, extra_context)
    

@admin.register(OrderCondition)
class OrderConditionAdmin(admin.ModelAdmin):
    fieldsets = (
        ("content", {
            'fields': (
                'text',
                'is_active',
                'updated_at',
            )
        }),
    )
    readonly_fields = ('updated_at',)

    def save_model(self, request, obj, form, change):
        try:
            obj.full_clean()
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            messages.error(request, f"error: {', '.join(e.messages)}")
            return

    def add_view(self, request, form_url='', extra_context=None):
        if OrderCondition.objects.exists():
            messages.warning(request, "There is some record now.if you want to change please deleted old record.then try again")
        return super().add_view(request, form_url, extra_context)