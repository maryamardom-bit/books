from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from orders.models import Order
from . import services


@login_required
@require_http_methods(['GET', 'POST'])
def payment_process(request):
    """Start (or retry) online payment for one of the current user's orders."""
    order_id = request.GET.get('order') or request.session.get('order_id')
    if not order_id or not str(order_id).isdigit():
        messages.error(request, _('No order found. Please try again.'))
        return redirect('cart:cart_detail')

    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.is_paid:
        messages.info(request, _('This order has already been paid.'))
        return redirect('page:home')

    callback_url = request.build_absolute_uri(reverse('payment:payment_verify'))
    try:
        gateway_redirect = services.start_payment(order, callback_url)
    except services.PaymentError as exc:
        messages.error(request, exc.message)
        return redirect('cart:cart_detail')

    if gateway_redirect is None:
        request.session.pop('order_id', None)
        messages.success(request, _('Payment successful'))
        return redirect('accounts:order_history')
    return redirect(gateway_redirect.url)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def payment_verify(request):
    """
    Gateway callback. The bank POSTs here cross-site, so the session cookie is usually
    absent (SameSite); the payment is identified by its reference, never by session/user.
    """
    data = request.POST if request.method == 'POST' else request.GET
    outcome = services.handle_callback(data)

    if outcome.success:
        request.session.pop('order_id', None)
        ref_id = outcome.payment.transaction_id or outcome.payment.reference
        messages.success(request, f'{outcome.message}! {_("Ref ID")}: {ref_id}')
        return redirect('page:home')

    messages.error(request, outcome.message)
    return redirect('cart:cart_detail')
