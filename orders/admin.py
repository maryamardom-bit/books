from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Order, OrderItem, ReturnRequest


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'user', 'status', 'datetime_created']
    list_filter = ['status', 'datetime_created']
    search_fields = ['order__id', 'user__username', 'reason']
    readonly_fields = ['datetime_created', 'datetime_updated']
    list_per_page = 20
    
    fieldsets = (
        ('Info', {'fields': ('order', 'user', 'status', 'reason', 'admin_note')}),
        ('Dates', {'fields': ('datetime_created', 'datetime_updated'), 'classes': ('collapse',)}),
    )
    
    actions = ['approve_returns', 'reject_returns', 'mark_as_returned']
    
    def approve_returns(self, request, queryset):
        """تایید درخواست‌های برگشت و افزایش موجودی"""
        count = 0
        for return_request in queryset:
            if return_request.status == ReturnRequest.ReturnStatus.PENDING:
                return_request.status = ReturnRequest.ReturnStatus.APPROVED
                return_request.save()
                
                # افزایش موجودی محصولات
                for item in return_request.order.items.all():
                    if item.product:
                        item.product.increase_stock(item.quantity)
                    elif item.package:
                        item.package.stock += item.quantity
                        item.package.save(update_fields=['stock'])
                
                # برگشت وجه به کیف پول
                return_request.user.wallet_balance += return_request.order.total_price
                return_request.user.save(update_fields=['wallet_balance'])
                
                count += 1
        
        self.message_user(request, f'{count} return requests approved.')
    approve_returns.short_description = _('Approve selected returns')
    
    def reject_returns(self, request, queryset):
        """رد درخواست‌های برگشت"""
        updated = queryset.filter(status=ReturnRequest.ReturnStatus.PENDING).update(
            status=ReturnRequest.ReturnStatus.REJECTED
        )
        self.message_user(request, f'{updated} return requests rejected.')
    reject_returns.short_description = _('Reject selected returns')
    
    def mark_as_returned(self, request, queryset):
        """علامت‌گذاری به عنوان برگشت داده شده"""
        updated = queryset.filter(status=ReturnRequest.ReturnStatus.APPROVED).update(
            status=ReturnRequest.ReturnStatus.RETURNED
        )
        self.message_user(request, f'{updated} marked as returned.')
    mark_as_returned.short_description = _('Mark as returned')