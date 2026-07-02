from django.contrib import admin
from .models import ContactInfo

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