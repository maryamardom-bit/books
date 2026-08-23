from functools import cached_property
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
        
        # Discount code
        self.discount_code = self.session.get('discount_code', None)
        self.discount_percent = self.session.get('discount_percent', 0)
        self.discount_amount = self.session.get('discount_amount', 0)
    
    def apply_discount_code(self, code):
        """Apply discount code"""
        from products.models import DiscountCode
        
        try:
            discount = DiscountCode.objects.get(code=code)
            if discount.is_valid():
                self.discount_code = code
                self.discount_percent = discount.percent
                self.discount_amount = discount.amount
                
                self.session['discount_code'] = code
                self.session['discount_percent'] = discount.percent
                self.session['discount_amount'] = discount.amount
                self.save()
                return True, _('Discount code applied.')
            else:
                return False, _('Invalid discount code.')
        except DiscountCode.DoesNotExist:
            return False, _('Discount code does not exist.')
    
    def remove_discount_code(self):
        """Remove discount code"""
        self.discount_code = None
        self.discount_percent = 0
        self.discount_amount = 0
        
        self.session.pop('discount_code', None)
        self.session.pop('discount_percent', None)
        self.session.pop('discount_amount', None)
        self.save()
    
    def get_discounted_total(self):
        """Total price with discount code applied"""
        total = self.get_total_price()
        
        if self.discount_amount > 0:
            return max(0, total - self.discount_amount)
        elif self.discount_percent > 0:
            discount = int(total * self.discount_percent / 100)
            return max(0, total - discount)
        
        return total
    
    def add(self, obj, quantity=1, replace_current_quantity=False, is_package=False):
        """Add product or package to cart"""
        item_key = f"{'package' if is_package else 'product'}_{obj.id}"
        
        if item_key not in self.cart:
            self.cart[item_key] = {'quantity': 0, 'is_package': is_package}
        
        if replace_current_quantity:
            self.cart[item_key]['quantity'] = quantity
        else:
            self.cart[item_key]['quantity'] += quantity
        
        self.save()

    def remove(self, obj, is_package=False):
        """Remove product or package from cart"""
        item_key = f"{'package' if is_package else 'product'}_{obj.id}"
        if item_key in self.cart:
            del self.cart[item_key]
            self.save()

    def save(self):
        """Mark session as modified"""
        self.session.modified = True

    @cached_property
    def items(self):
        """Get cart items cached"""
        cart = self.cart.copy()
        product_ids = []
        package_ids = []
        
        for key in cart.keys():
            if key.startswith('product_'):
                product_ids.append(key.replace('product_', ''))
            elif key.startswith('package_'):
                package_ids.append(key.replace('package_', ''))
        
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
        packages = {p.id: p for p in Package.objects.filter(id__in=package_ids)}
        
        items = []
        for key, item_data in cart.items():
            if key.startswith('product_'):
                product_id = int(key.replace('product_', ''))
                product = products.get(product_id)
                if product:
                    price = product.get_discounted_price()
                    items.append({
                        'key': key,
                        'product_obj': product,
                        'package_obj': None,
                        'title': product.title,
                        'price': price,
                        'original_price': product.price,
                        'image': product.image,
                        'weight': product.weight or 0,
                        'is_package': False,
                        'quantity': item_data['quantity'],
                        'total_price': price * item_data['quantity'],
                    })
            elif key.startswith('package_'):
                package_id = int(key.replace('package_', ''))
                package = packages.get(package_id)
                if package:
                    items.append({
                        'key': key,
                        'product_obj': None,
                        'package_obj': package,
                        'title': package.title,
                        'price': package.price,
                        'original_price': package.original_price,
                        'image': package.image,
                        'weight': package.get_total_weight(),
                        'is_package': True,
                        'quantity': item_data['quantity'],
                        'total_price': package.price * item_data['quantity'],
                    })
        
        return items
    
    def __iter__(self):
        return iter(self.items)
    
    def __len__(self):
        return sum(item['quantity'] for item in self.items)
    
    def clear(self):
        """Clear cart and release reserved stock"""
        for item in self.items:
            if not item['is_package'] and item['product_obj']:
                item['product_obj'].release_stock(item['quantity'])
        
        self.session.pop('cart', None)
        self.save()
    
    def get_total_price(self):
        """Get total price"""
        return sum(item['total_price'] for item in self.items)
    
    def get_total_price_without_discount(self):
        """Get total price without discount"""
        return sum(item['original_price'] * item['quantity'] for item in self.items)
    
    def get_total_savings(self):
        """Get total savings"""
        return self.get_total_price_without_discount() - self.get_total_price()
    
    def get_total_weight(self):
        """Get total weight"""
        return sum(item['weight'] * item['quantity'] for item in self.items)
    
    def is_empty(self):
        """Check if cart is empty"""
        return len(self.items) == 0