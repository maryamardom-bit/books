from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from cart.cart import Cart
from .forms import OrderForm, ReturnRequestForm
from .models import Order, OrderItem, ReturnRequest
from services.sms import SMSService


@login_required
def order_create_view(request):
    """Create new order from cart"""
    order_form = OrderForm()
    cart = Cart(request)

    if cart.is_empty():
        messages.warning(request, _('Your cart is empty.'))
        return redirect('product:product_list')

    if request.method == 'POST':
        order_form = OrderForm(request.POST)

        if order_form.is_valid():
            order_obj = order_form.save(commit=False)
            order_obj.user = request.user
            order_obj.save()

            total_weight = 0
            total_price = 0

            for item in cart:
                price = item['price']
                quantity = item['quantity']

                if item['is_package']:
                    package = item.get('package_obj')
                    if package:
                        OrderItem.objects.create(
                            order=order_obj,
                            package=package,
                            quantity=quantity,
                            price=price,
                        )
                        total_weight += package.get_total_weight() * quantity
                else:
                    product = item.get('product_obj')
                    if product:
                        OrderItem.objects.create(
                            order=order_obj,
                            product=product,
                            quantity=quantity,
                            price=price,
                        )
                        total_weight += (product.weight or 0) * quantity

                total_price += price * quantity

            order_obj.total_weight = total_weight
            order_obj.total_price = total_price
            order_obj.save()

            # Decrease stock
            for item in cart:
                if not item['is_package']:
                    product = item.get('product_obj')
                    if product:
                        product.decrease_stock(item['quantity'])
                else:
                    package = item.get('package_obj')
                    if package:
                        package.stock -= item['quantity']
                        package.save(update_fields=['stock'])

            cart.clear()

            request.user.first_name = order_obj.first_name
            request.user.last_name = order_obj.last_name
            request.user.save()

            request.session['order_id'] = order_obj.id

            # Send order confirmation SMS
            if request.user.phone_number:
                SMSService.send_order_confirmation_sms(request.user, order_obj)

            return redirect('payment:payment_process')
        else:
            messages.error(request, _('Please correct the errors below.'))

    return render(request, 'orders/order_create.html', {
        'form': order_form,
    })


@login_required
def request_return_view(request, order_id):
    """User submits return request"""
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if not order.is_paid:
        messages.error(request, _('This order is not paid.'))
        return redirect('accounts:order_history')

    days_since_order = (timezone.now() - order.datetime_created).days
    if days_since_order > 3:
        messages.error(request, _('Return period has expired (3 days).'))
        return redirect('accounts:order_history')

    existing_return = ReturnRequest.objects.filter(order=order, user=request.user).first()
    if existing_return:
        messages.warning(request, _('You already have a return request for this order.'))
        return redirect('accounts:order_history')

    if request.method == 'POST':
        form = ReturnRequestForm(request.POST)
        if form.is_valid():
            return_request = form.save(commit=False)
            return_request.order = order
            return_request.user = request.user
            return_request.status = ReturnRequest.ReturnStatus.PENDING
            return_request.save()

            messages.success(request, _('Your return request has been submitted.'))
            return redirect('accounts:order_history')
    else:
        form = ReturnRequestForm()

    return render(request, 'orders/request_return.html', {
        'form': form,
        'order': order,
    })


@login_required
def my_returns_view(request):
    """List user's return requests"""
    returns = ReturnRequest.objects.filter(user=request.user).order_by('-datetime_created')

    return render(request, 'orders/my_returns.html', {
        'returns': returns,
    })