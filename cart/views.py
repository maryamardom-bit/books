from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.translation import gettext as _

from products.models import Product
from .cart import Cart
from .forms import AddToCartProductForm


def cart_detail_view(request):
    cart = Cart(request)

    for item in cart:
        item['product_update_quantity_form'] = AddToCartProductForm(initial={
            'quantity': item['quantity'],
            'inplace': True,
        })

    return render(request, 'cart/cart_detail.html', {
        'cart': cart,
    })


@require_POST
def add_to_cart_view(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    form = AddToCartProductForm(request.POST)

    if form.is_valid():
        cleaned_data = form.cleaned_data
        quantity = cleaned_data['quantity']
        replace_current = cleaned_data['inplace']
        
        # Check if product already in cart
        product_id_str = str(product.id)
        was_in_cart = product_id_str in cart.cart
        
        cart.add(product, quantity, replace_current_quantity=replace_current)
        
        if replace_current:
            messages.success(request, _('Product successfully updated in cart.'))
        else:
            messages.success(request, _('Product successfully added to cart.'))
    else:
        messages.error(request, _('Invalid quantity. Please try again.'))

    return redirect('cart:cart_detail')


def remove_from_cart(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)

    cart.remove(product)
    messages.success(request, _('Product successfully removed from cart.'))

    return redirect('cart:cart_detail')


@require_POST
def clear_cart(request):
    cart = Cart(request)

    if len(cart):
        cart.clear()
        messages.success(request, _('All products successfully removed from your cart.'))
    else:
        messages.warning(request, _('Your cart is already empty.'))

    return redirect('product:product_list')