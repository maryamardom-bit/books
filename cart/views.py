from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from products.models import Product, Package
from .cart import Cart
from .forms import AddToCartProductForm


def cart_detail_view(request):
    cart = Cart(request)

    for item in cart:
        item['product_update_quantity_form'] = AddToCartProductForm(initial={
            'quantity': item['quantity'],
            'inplace': True,
        })

    context = {
        'cart': cart,
        'total_price': cart.get_total_price(),
        'total_savings': cart.get_total_savings(),
        'total_weight': cart.get_total_weight(),
        'discounted_total': cart.get_discounted_total(),
    }

    return render(request, 'cart/cart_detail.html', context)


@require_POST
def add_to_cart_view(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    form = AddToCartProductForm(request.POST)

    if form.is_valid():
        cleaned_data = form.cleaned_data
        quantity = cleaned_data['quantity']
        replace_current = cleaned_data['inplace']
        
        cart.add(product, quantity, replace_current_quantity=replace_current, is_package=False)
        
        if replace_current:
            messages.success(request, _('Product updated in cart.'))
        else:
            messages.success(request, _('Product added to cart.'))
    else:
        messages.error(request, _('Invalid quantity.'))

    return redirect('cart:cart_detail')


@require_POST
def add_package_to_cart_view(request, package_id):
    cart = Cart(request)
    package = get_object_or_404(Package, id=package_id)
    form = AddToCartProductForm(request.POST)

    if form.is_valid():
        quantity = form.cleaned_data['quantity']
        cart.add(package, quantity, replace_current_quantity=False, is_package=True)
        messages.success(request, _('Package added to cart.'))
    else:
        messages.error(request, _('Invalid quantity.'))

    return redirect('cart:cart_detail')


def remove_from_cart(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product, is_package=False)
    messages.success(request, _('Product removed from cart.'))
    return redirect('cart:cart_detail')


def remove_package_from_cart(request, package_id):
    cart = Cart(request)
    package = get_object_or_404(Package, id=package_id)
    cart.remove(package, is_package=True)
    messages.success(request, _('Package removed from cart.'))
    return redirect('cart:cart_detail')


@require_POST
def clear_cart(request):
    cart = Cart(request)
    if len(cart):
        cart.clear()
        messages.success(request, _('Cart cleared.'))
    else:
        messages.warning(request, _('Cart is already empty.'))
    return redirect('product:product_list')


@require_POST
def apply_discount_code_view(request):
    """Apply discount code"""
    cart = Cart(request)
    code = request.POST.get('code', '').strip()
    
    if code:
        success, message = cart.apply_discount_code(code)
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
    
    return redirect('cart:cart_detail')


def remove_discount_code_view(request):
    """Remove discount code"""
    cart = Cart(request)
    cart.remove_discount_code()
    messages.info(request, _('Discount code removed.'))
    return redirect('cart:cart_detail')