from django.utils.translation import gettext_lazy as _
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
        """
        Add product or package to cart.
        """
        item_key = f"{'package' if is_package else 'product'}_{obj.id}"
        
        if item_key not in self.cart:
            self.cart[item_key] = {
                'quantity': 0,
                'is_package': is_package,
            }
        
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

    def __iter__(self):
        cart = self.cart.copy()
        
        product_ids = [key.replace('product_', '') for key in cart.keys() if key.startswith('product_')]
        package_ids = [key.replace('package_', '') for key in cart.keys() if key.startswith('package_')]
        
        products = Product.objects.filter(id__in=product_ids)
        packages = Package.objects.filter(id__in=package_ids)
        
        for product in products:
            key = f'product_{product.id}'
            cart[key]['product_obj'] = product
            cart[key]['title'] = product.title
            cart[key]['price'] = product.get_discounted_price()
            cart[key]['image'] = product.image
        
        for package in packages:
            key = f'package_{package.id}'
            cart[key]['package_obj'] = package
            cart[key]['title'] = package.title
            cart[key]['price'] = package.price
            cart[key]['image'] = package.image
        
        for item in cart.values():
            item['total_price'] = item['price'] * item['quantity']
            yield item

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        return sum(item['total_price'] for item in self)

    def clear(self):
        del self.session['cart']
        self.save()

    def is_empty(self):
        return len(self.cart) == 0

    def save(self):
        self.session.modified = True