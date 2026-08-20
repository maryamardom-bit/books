import json
import requests
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _

from orders.models import Order


def payment_process(request):
    """
    شروع فرآیند پرداخت با زرین‌پال
    """
    # Get order id from session
    order_id = request.session.get('order_id')
    
    if not order_id:
        messages.error(request, _('No order found. Please try again.'))
        return redirect('cart:cart_detail')

    # Get the order object
    order = get_object_or_404(Order, id=order_id)
    
    # Check if order is already paid
    if order.is_paid:
        messages.info(request, _('This order has already been paid.'))
        return redirect('page:home')

    toman_total_price = order.get_total_price()
    rial_total_price = toman_total_price * 10

    zarinpal_request_url = 'https://payment.zarinpal.com/pg/v4/payment/request.json'

    request_header = {
        'accept': 'application/json',
        'content-type': 'application/json',
    }

    request_data = {
        'merchant_id': settings.ZARINPAL_MERCHANT_ID,
        'amount': rial_total_price,
        'description': f'Order #{order.id} - {order.user.username}',
        'callback_url': request.build_absolute_uri('/payment/verify/'),
    }

    try:
        response = requests.post(
            url=zarinpal_request_url,
            data=json.dumps(request_data),
            headers=request_header,
            timeout=10,
        )
        
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('data'):
            authority = response_data['data'].get('authority')
            if authority:
                return redirect(f'https://payment.zarinpal.com/pg/StartPay/{authority}')
            else:
                messages.error(request, _('Payment gateway error. Please try again.'))
        else:
            error_message = response_data.get('errors', {}).get('message', _('Unknown error'))
            messages.error(request, f'{_("Payment error")}: {error_message}')
            
    except requests.exceptions.Timeout:
        messages.error(request, _('Payment gateway timeout. Please try again.'))
    except requests.exceptions.RequestException as e:
        messages.error(request, f'{_("Connection error")}: {str(e)}')
    except json.JSONDecodeError:
        messages.error(request, _('Invalid response from payment gateway.'))

    return redirect('cart:cart_detail')


@csrf_exempt
@require_http_methods(["GET", "POST"])
def payment_verify(request):
    """
    Verify payment from Zarinpal callback
    """
    authority = request.GET.get('Authority')
    status = request.GET.get('Status')
    
    if not authority or status != 'OK':
        messages.error(request, _('Payment was cancelled or failed.'))
        return redirect('cart:cart_detail')
    
    order_id = request.session.get('order_id')
    if not order_id:
        messages.error(request, _('No order found.'))
        return redirect('cart:cart_detail')
    
    order = get_object_or_404(Order, id=order_id)
    
    toman_total_price = order.get_total_price()
    rial_total_price = toman_total_price * 10
    
    zarinpal_verify_url = 'https://payment.zarinpal.com/pg/v4/payment/verify.json'
    
    request_header = {
        'accept': 'application/json',
        'content-type': 'application/json',
    }
    
    request_data = {
        'merchant_id': settings.ZARINPAL_MERCHANT_ID,
        'amount': rial_total_price,
        'authority': authority,
    }
    
    try:
        response = requests.post(
            url=zarinpal_verify_url,
            data=json.dumps(request_data),
            headers=request_header,
            timeout=10,
        )
        
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('data'):
            data = response_data['data']
            if data.get('code') == 100:
                # Payment successful
                order.is_paid = True
                order.save()
                
                # Clear session
                if 'order_id' in request.session:
                    del request.session['order_id']
                
                ref_id = data.get('ref_id', '')
                messages.success(request, _('Payment successful! Reference ID: {}').format(ref_id))
                return redirect('page:home')
            else:
                messages.error(request, _('Payment verification failed.'))
        else:
            messages.error(request, _('Payment verification error.'))
            
    except requests.exceptions.RequestException:
        messages.error(request, _('Connection error during verification.'))
    except json.JSONDecodeError:
        messages.error(request, _('Invalid response from payment gateway.'))

    return redirect('cart:cart_detail')