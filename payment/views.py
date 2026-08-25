import requests
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from orders.models import Order
from services.sms import SMSService


def payment_process(request):
    """Start payment process with SEP gateway"""
    order_id = request.session.get('order_id')
    
    if not order_id:
        messages.error(request, _('No order found. Please try again.'))
        return redirect('cart:cart_detail')
    
    order = get_object_or_404(Order, id=order_id)
    
    if order.is_paid:
        messages.info(request, _('This order has already been paid.'))
        return redirect('page:home')
    
    amount = order.total_price
    
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
                error_desc = response_data.get('errorDesc', _('Unknown error'))
                messages.error(request, f'{_("Payment error")}: {error_desc}')
        else:
            messages.error(request, _('Error connecting to payment gateway.'))
            
    except requests.exceptions.Timeout:
        messages.error(request, _('Payment gateway timeout.'))
    except requests.exceptions.RequestException as e:
        messages.error(request, f'{_("Connection error")}: {str(e)}')
    
    return redirect('cart:cart_detail')


@csrf_exempt
@require_http_methods(["GET", "POST"])
def payment_verify(request):
    """Verify payment from SEP gateway"""
    if request.method == 'GET':
        token = request.GET.get('token')
        rrn = request.GET.get('RRN')
        status = request.GET.get('status')
    else:
        token = request.POST.get('token')
        rrn = request.POST.get('RRN')
        status = request.POST.get('status')
    
    if status != '2' or not token:
        messages.error(request, _('Payment failed or cancelled.'))
        return redirect('cart:cart_detail')
    
    order_id = request.session.get('order_id')
    if not order_id:
        messages.error(request, _('No order found.'))
        return redirect('cart:cart_detail')
    
    order = get_object_or_404(Order, id=order_id)
    
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
                order.is_paid = True
                order.save()
                
                # Decrease stock
                for item in order.items.all():
                    if item.product:
                        item.product.decrease_stock(item.quantity)
                    elif item.package:
                        item.package.stock -= item.quantity
                        item.package.save(update_fields=['stock'])
                
                # Advance tiered discount
                from products.models import TieredDiscount
                tiered, created = TieredDiscount.objects.get_or_create(user=order.user)
                tiered.advance_tier()
                
                # Clear session
                if 'order_id' in request.session:
                    del request.session['order_id']
                
                # Send payment confirmation SMS
                if order.user.phone_number:
                    SMSService.send_payment_confirmation_sms(order.user, order)
                
                ref_id = response_data.get('RefId', '')
                messages.success(request, f'{_("Payment successful")}! {_("Ref ID")}: {ref_id}')
                return redirect('page:home')
            else:
                messages.error(request, _('Payment verification failed.'))
        else:
            messages.error(request, _('Error in payment verification.'))
            
    except requests.exceptions.RequestException:
        messages.error(request, _('Connection error during verification.'))
    
    return redirect('cart:cart_detail')