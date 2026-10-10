from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'gateway', 'amount', 'status', 'transaction_id', 'created_at', 'paid_at']
    list_filter = ['status', 'gateway', 'created_at']
    search_fields = ['transaction_id', 'rrn', 'order__user__username', 'order__phone_number']
    list_select_related = ['order']
    list_per_page = 30

    # Payments are written only by payment.services; the admin is a read-only audit view.
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
