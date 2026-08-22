from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from products.models import Product, Package


class Cart:
    def __init__(self, request):
        self.request = request
        self.session = request.session
        
        cart = self.session.get('cart')
        if not cart:
            cart = self.session['cart'] = {}
        self.cart = cart

    def add(self, obj, quantity=1, replace_current_quantity=False, is_package=False):
        item_key = f"{'package' if is_package else 'product'}_{obj.id}"
        
        if item_key not in self.cart:
            self.cart[item_key] = {'quantity': 0, 'is_package': is_package}
        
        if replace_current_quantity:
            self.cart[item_key]['quantity'] = quantity
        else:
            self.cart[item_key]['quantity'] += quantity
        
        self.save()

    def remove(self, obj, is_package=False):
        item_key = f"{'package' if is_package else 'product'}_{obj.id}"
        if item_key in self.cart:
            del self.cart[item_key]
            self.save()

    def save(self):
        self.session.modified = True

    @cached_property
    def _items(self):
        """آماده‌سازی آیتم‌ها فقط یک بار"""
        cart = self.cart.copy()
        
        product_ids = [k.replace('product_', '') for k in cart if k.startswith('product_')]
        package_ids = [k.replace('package_', '') for k in cart if k.startswith('package_')]
        
        products = Product.objects.filter(id__in=product_ids)
        packages = Package.objects.filter(id__in=package_ids)
        
        for product in products:
            key = f'product_{product.id}'
            cart[key]['product_obj'] = product
            cart[key]['title'] = product.title
            cart[key]['price'] = product.get_discounted_price()
            cart[key]['original_price'] = product.price
            cart[key]['image'] = product.image
            cart[key]['weight'] = product.weight or 0
            cart[key]['is_package'] = False
        
        for package in packages:
            key = f'package_{package.id}'
            cart[key]['package_obj'] = package
            cart[key]['title'] = package.title
            cart[key]['price'] = package.price
            cart[key]['original_price'] = package.original_price
            cart[key]['image'] = package.image
            cart[key]['weight'] = package.get_total_weight()
            cart[key]['is_package'] = True
        
        for item in cart.values():
            item['total_price'] = item['price'] * item['quantity']
        
        return list(cart.values())

    def __iter__(self):
        for item in self._items:
            yield item

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())

    def clear(self):
        del self.session['cart']
        self.save()

    def get_total_price(self):
        return sum(item['total_price'] for item in self._items)

    def get_total_price_without_discount(self):
        return sum(item['original_price'] * item['quantity'] for item in self._items)

    def get_total_savings(self):
        return self.get_total_price_without_discount() - self.get_total_price()

    def get_total_weight(self):
        return sum(item['weight'] * item['quantity'] for item in self._items)

    def is_empty(self):
        return len(self.cart) == 0
    