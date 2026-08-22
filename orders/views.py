from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _

from cart.cart import Cart
from .forms import OrderForm
from .models import Order, OrderItem


@login_required
def order_create_view(request):
    order_form = OrderForm()
    cart = Cart(request)

    if len(cart) == 0:
        messages.warning(request, _("سبد خرید شما خالی است."))
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

            cart.clear()

            request.user.first_name = order_obj.first_name
            request.user.last_name = order_obj.last_name
            request.user.save()

            request.session['order_id'] = order_obj.id
            return redirect('payment:payment_process')
        else:
            messages.error(request, _('لطفاً خطاهای فرم را اصلاح کنید.'))

    return render(request, 'orders/order_create.html', {
        'form': order_form,
    })
    new_func(order_form)
    cart = Cart(request)

    if len(cart) == 0:
        messages.warning(request, _("You can't proceed to checkout because your cart is empty."))
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
                if item.get('is_package'):
                    # آیتم پکیج
                    package = item.get('package_obj')
                    if package:
                        OrderItem.objects.create(
                            order=order_obj,
                            package=package,
                            quantity=item['quantity'],
                            price=item['price'],
                        )
                        total_weight += package.get_total_weight() * item['quantity']
                        total_price += item['price'] * item['quantity']
                else:
                    # آیتم محصول عادی
                    product = item.get('product_obj')
                    if product:
                        OrderItem.objects.create(
                            order=order_obj,
                            product=product,
                            quantity=item['quantity'],
                            price=product.get_discounted_price(),
                        )
                        total_weight += (product.weight or 0) * item['quantity']
                        total_price += product.get_discounted_price() * item['quantity']

            # ذخیره وزن و قیمت کل
            order_obj.total_weight = total_weight
            order_obj.total_price = total_price
            order_obj.save()

            cart.clear()

            request.user.first_name = order_obj.first_name
            request.user.last_name = order_obj.last_name
            request.user.save()

            request.session['order_id'] = order_obj.id
            return redirect('payment:payment_process')
        else:
            messages.error(request, _('Please correct the errors below.'))

    return render(request, 'orders/order_create.html', {
        'form': order_form,
    })

def new_func(order_form):
    order_form = OrderForm()


