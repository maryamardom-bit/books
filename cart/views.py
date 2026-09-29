from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

from persian_translate.templatetags.persian_translation_tags import translate_number
from products.models import Product, Package
from .cart import Cart
from .forms import AddToCartProductForm


def _money(value):
    return translate_number(f'{int(value):,}')


def _related_books(cart):
    categories = []
    exclude_ids = []
    for item in cart:
        product = item.get('product_obj')
        if product:
            exclude_ids.append(product.id)
            categories.append(product.category)
        package = item.get('package_obj')
        if package:
            for bundled in package.products.all():
                exclude_ids.append(bundled.id)
                categories.append(bundled.category)

    books = Product.objects.with_ratings().filter(active=True).exclude(id__in=exclude_ids)
    if categories:
        related = books.filter(category__in=categories)
        if related.exists():
            books = related
    return books.order_by('-datetime_created')[:4]


def cart_detail_view(request):
    cart = Cart(request)
    for note in cart.reconcile():
        messages.warning(request, note)

    total_price = cart.get_total_price()
    discounted_total = cart.get_discounted_total()
    context = {
        'cart': cart,
        'total_price': total_price,
        'total_savings': cart.get_total_savings(),
        'discount_amount': max(total_price - discounted_total, 0),
        'discounted_total': discounted_total,
        'suggested_books': (
            _related_books(cart)
            if len(cart)
            else Product.objects.with_ratings().filter(active=True).order_by('-datetime_created')[:4]
        ),
    }

    return render(request, 'cart/cart_detail.html', context)


def _wants_json(request):
    """Catalog buttons post with fetch and expect JSON."""
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def _summary_payload(cart):
    total_price = cart.get_total_price()
    discounted_total = cart.get_discounted_total()
    savings = cart.get_total_savings()
    discount_amount = max(total_price - discounted_total, 0)
    return {
        'cart_count': len(cart),
        'items_label': translate_number(len(cart)),
        'total_price': _money(total_price),
        'savings': _money(savings),
        'savings_amount': savings,
        'discount': _money(discount_amount),
        'discount_amount': discount_amount,
        'final_price': _money(discounted_total),
        'show_final': discounted_total != total_price,
    }


def _line_state(cart, item, is_package):
    for row in cart:
        obj = row.get('package_obj') if is_package else row.get('product_obj')
        if bool(row.get('is_package')) != bool(is_package) or obj is None or obj.id != item.id:
            continue
        key = row['key']
        limit = int(row.get('stock_limit') or 0)
        low = 0 < limit <= 3
        if low:
            note = _('Only %(count)s left') % {'count': translate_number(limit)}
        elif limit > 0:
            note = _('In stock')
        else:
            note = _('Out of stock')
        return {
            'key': key,
            'removed': False,
            'quantity': translate_number(row['quantity']),
            'quantity_raw': row['quantity'],
            'line_total': _money(row['total_price']),
            'at_stock_limit': row['quantity'] >= limit,
            'stock_note': note,
            'stock_low': low,
        }
    return {'key': f"{'package' if is_package else 'product'}_{item.id}", 'removed': True}


def _cart_response(request, cart, message, *, ok=True, kind=None, item=None, is_package=False):
    if kind is None:
        kind = 'success' if ok else 'error'
    if _wants_json(request):
        payload = {
            'ok': ok,
            'message': message,
            'kind': kind,
        }
        payload.update(_summary_payload(cart))
        if item is not None:
            payload['line'] = _line_state(cart, item, is_package)
        return JsonResponse(payload, status=200 if ok else 400)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return _redirect_back(request)


def _add_message(status, limit):
    if status == 'out_of_stock':
        return _('This title is out of stock.'), False
    if status == 'limited':
        return _('Only %(count)s left in stock.') % {'count': translate_number(limit)}, True
    return None, True


def _redirect_back(request):
    target = request.POST.get('next') or request.META.get('HTTP_REFERER', '')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect('cart:cart_detail')


@require_POST
def add_to_cart_view(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    form = AddToCartProductForm(request.POST)

    if form.is_valid():
        cleaned_data = form.cleaned_data
        quantity = cleaned_data['quantity']
        replace_current = cleaned_data['inplace']
        status = cart.add(product, quantity, replace_current_quantity=replace_current, is_package=False)
        stock_message, ok = _add_message(status, cart._stock_limit(product, False))
        if stock_message and not ok:
            return _cart_response(request, cart, stock_message, ok=False, item=product, is_package=False)
        if replace_current:
            message = _('Product updated in cart.')
        else:
            message = _('Added to cart.')
        if stock_message:
            message = stock_message
    else:
        return _cart_response(request, cart, _('Invalid quantity.'), ok=False, item=product, is_package=False)

    return _cart_response(request, cart, message, item=product, is_package=False)


@require_POST
def add_package_to_cart_view(request, package_id):
    cart = Cart(request)
    package = get_object_or_404(Package, id=package_id)
    form = AddToCartProductForm(request.POST)

    if form.is_valid():
        quantity = form.cleaned_data['quantity']
        status = cart.add(
            package,
            quantity,
            replace_current_quantity=form.cleaned_data['inplace'],
            is_package=True,
        )
        stock_message, ok = _add_message(status, cart._stock_limit(package, True))
        if stock_message and not ok:
            return _cart_response(request, cart, stock_message, ok=False, item=package, is_package=True)
        if form.cleaned_data['inplace']:
            message = _('Product updated in cart.')
        else:
            message = _('Added to cart.')
        if stock_message:
            message = stock_message
    else:
        return _cart_response(request, cart, _('Invalid quantity.'), ok=False, item=package, is_package=True)

    return _cart_response(request, cart, message, item=package, is_package=True)


def _decrease_response(request, cart, status, item, is_package):
    if status == 'missing':
        return _cart_response(
            request, cart, _('This item is not in your cart.'), ok=False, kind='error',
            item=item, is_package=is_package,
        )
    if status == 'removed':
        return _cart_response(
            request, cart, _('Removed from cart.'), kind='removed',
            item=item, is_package=is_package,
        )
    return _cart_response(
        request, cart, _('Removed one from cart.'), kind='removed',
        item=item, is_package=is_package,
    )


@require_POST
def decrease_from_cart(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    return _decrease_response(request, cart, cart.decrease(product, is_package=False), product, False)


@require_POST
def decrease_package_from_cart(request, package_id):
    cart = Cart(request)
    package = get_object_or_404(Package, id=package_id)
    return _decrease_response(request, cart, cart.decrease(package, is_package=True), package, True)


@require_POST
def remove_from_cart(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product, is_package=False)
    return _cart_response(
        request, cart, _('Product removed from cart.'), kind='removed',
        item=product, is_package=False,
    )


@require_POST
def remove_package_from_cart(request, package_id):
    cart = Cart(request)
    package = get_object_or_404(Package, id=package_id)
    cart.remove(package, is_package=True)
    return _cart_response(
        request, cart, _('Package removed from cart.'), kind='removed',
        item=package, is_package=True,
    )


@require_POST
def clear_cart(request):
    cart = Cart(request)
    if len(cart):
        cart.clear()
        messages.success(request, _('Cart cleared.'))
    else:
        messages.warning(request, _('Cart is already empty.'))
    return redirect('cart:cart_detail')


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
    else:
        messages.error(request, _('Enter a discount code.'))

    return redirect('cart:cart_detail')


def remove_discount_code_view(request):
    """Remove discount code"""
    cart = Cart(request)
    cart.remove_discount_code()
    messages.info(request, _('Discount code removed.'))
    return redirect('cart:cart_detail')