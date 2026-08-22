import requests
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _
from django.urls import reverse

from orders.models import Order


def payment_process(request):
    """شروع فرآیند پرداخت با درگاه SEP"""
    order_id = request.session.get('order_id')
    
    if not order_id:
        messages.error(request, _('سفارشی پیدا نشد. لطفاً دوباره تلاش کنید.'))
        return redirect('cart:cart_detail')
    
    order = get_object_or_404(Order, id=order_id)
    
    if order.is_paid:
        messages.info(request, _('این سفارش قبلاً پرداخت شده است.'))
        return redirect('page:home')
    
    amount = order.total_price  # تومان
    
    # SEP API
    sep_request_url = 'https://sep.shaparak.ir/onlinepg/onlinepg'
    
    callback_url = request.build_absolute_uri(reverse('payment:payment_verify'))
    
    data = {
        'TerminalId': settings.SEP_TERMINAL_ID,
        'Amount': amount,
        'callbackUrl': callback_url,
        'InvoiceId': str(order.id),
        'Payload': f'Order #{order.id}',
    }
    
    try:
        response = requests.post(sep_request_url, data=data, timeout=15)
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('status') == 1:
                token = response_data.get('token')
                return redirect(f'https://sep.shaparak.ir/OnlinePG/SendToken?token={token}')
            else:
                error_desc = response_data.get('errorDesc', _('خطای ناشناخته'))
                messages.error(request, f'{_("خطای پرداخت")}: {error_desc}')
        else:
            messages.error(request, _('خطا در ارتباط با درگاه پرداخت.'))
            
    except requests.exceptions.Timeout:
        messages.error(request, _('مهلت ارتباط با درگاه به پایان رسید.'))
    except requests.exceptions.RequestException as e:
        messages.error(request, f'{_("خطای ارتباط")}: {str(e)}')
    
    return redirect('cart:cart_detail')


@csrf_exempt
@require_http_methods(["GET", "POST"])
def payment_verify(request):
    """تأیید پرداخت از درگاه SEP"""
    if request.method == 'GET':
        token = request.GET.get('token')
        rrn = request.GET.get('RRN')
        status = request.GET.get('status')
    else:
        token = request.POST.get('token')
        rrn = request.POST.get('RRN')
        status = request.POST.get('status')
    
    if status != '2' or not token:
        messages.error(request, _('پرداخت ناموفق بود یا لغو شد.'))
        return redirect('cart:cart_detail')
    
    order_id = request.session.get('order_id')
    if not order_id:
        messages.error(request, _('سفارشی پیدا نشد.'))
        return redirect('cart:cart_detail')
    
    order = get_object_or_404(Order, id=order_id)
    
    # تأیید نهایی
    sep_verify_url = 'https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction'
    
    data = {
        'TerminalId': settings.SEP_TERMINAL_ID,
        'token': token,
        'RRN': rrn,
    }
    
    try:
        response = requests.post(sep_verify_url, data=data, timeout=15)
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('status') == 1:
                # پرداخت موفق
                order.is_paid = True
                order.save()
                
                # کاهش موجودی
                for item in order.items.all():
                    if item.product:
                        item.product.decrease_stock(item.quantity)
                    elif item.package:
                        item.package.stock -= item.quantity
                        item.package.save(update_fields=['stock'])
                
                # ارتقا تخفیف پلکانی
                from products.models import TieredDiscount
                tiered, created = TieredDiscount.objects.get_or_create(user=order.user)
                tiered.advance_tier()
                
                # پاک کردن سشن
                if 'order_id' in request.session:
                    del request.session['order_id']
                
                ref_id = response_data.get('RefId', '')
                messages.success(request, f'پرداخت موفق! کد پیگیری: {ref_id}')
                return redirect('page:home')
            else:
                messages.error(request, _('تأیید پرداخت ناموفق بود.'))
        else:
            messages.error(request, _('خطا در تأیید پرداخت.'))
            
    except requests.exceptions.RequestException:
        messages.error(request, _('خطای ارتباط در تأیید پرداخت.'))
    
    return redirect('cart:cart_detail')