# cart/cart.py
from django.conf import settings
from decimal import Decimal
from products.models import Product, Package, DiscountCode


class Cart:
    def __init__(self, request):
        """
        Initialize the cart.
        """
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            # save an empty cart in the session
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart
        self.discount_code = self.cart.get('discount_code')
        self.discount_percent = self.cart.get('discount_percent', 0)
        self.discount_amount = self.cart.get('discount_amount', 0)
    
    def add(self, item, quantity=1, replace_current_quantity=False, is_package=False):
        """
        Add a product or package to the cart or update its quantity.
        """
        item_type = 'package' if is_package else 'product'
        item_id = str(item.id)
        
        # محاسبه وزن مناسب
        if is_package:
            weight = item.get_total_weight()
        else:
            weight = item.weight if item.weight else 0
        
        if item_id not in self.cart:
            self.cart[item_id] = {
                'quantity': 0,
                'price': str(item.price),
                'item_type': item_type,
                'is_package': is_package,  # اضافه کردن is_package
                'title': item.title,
                'weight': str(weight),
            }
        
        if replace_current_quantity:
            self.cart[item_id]['quantity'] = quantity
        else:
            self.cart[item_id]['quantity'] += quantity
        
        self.save()
    
    def save(self):
        # به‌روزرسانی session
        self.session[settings.CART_SESSION_ID] = self.cart
        self.session.modified = True
    
    def remove(self, item, is_package=False):
        """
        Remove a product from the cart.
        """
        item_id = str(item.id)
        if item_id in self.cart:
            del self.cart[item_id]
            self.save()
    
    def __iter__(self):
        """
        Iterate over the items in the cart and get the products from the database.
        """
        cart_items = self.cart.copy()
        
        product_ids = []
        package_ids = []
        
        for item_id, item_data in cart_items.items():
            if isinstance(item_data, dict):
                if item_data.get('item_type') == 'package':
                    package_ids.append(int(item_id))
                else:
                    product_ids.append(int(item_id))
        
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
        packages = {p.id: p for p in Package.objects.filter(id__in=package_ids)}
        
        for item_id, item_data in cart_items.items():
            if not isinstance(item_data, dict):
                continue
            
            item_id_int = int(item_id)
            quantity = item_data['quantity']
            
            if item_data.get('item_type') == 'package':
                package = packages.get(item_id_int)
                if package:
                    item_data['package_obj'] = package
                    item_data['is_package'] = True
                    item_data['price'] = str(package.price)
                    item_data['total_price'] = package.price * quantity
            else:
                product = products.get(item_id_int)
                if product:
                    item_data['product_obj'] = product
                    item_data['is_package'] = False
                    item_data['price'] = str(product.get_discounted_price())
                    item_data['total_price'] = product.get_discounted_price() * quantity
            
            item_data['price'] = Decimal(item_data['price'])
            item_data['total_price'] = item_data['price'] * quantity
            yield item_data
    
    def __len__(self):
        """
        Count all items in the cart.
        """
        return sum(item['quantity'] for item_id, item in self.cart.items() if isinstance(item, dict))
    
    def get_total_price(self):
        """
        Calculate total price of items in cart.
        """
        total = 0
        for item in self:
            total += item['total_price']
        return int(total)
    
    def get_total_weight(self):
        """
        Calculate total weight of items in cart.
        """
        total_weight = 0
        for item in self:
            if item.get('product_obj'):
                weight = item['product_obj'].weight or 0
            elif item.get('package_obj'):
                weight = item['package_obj'].get_total_weight()
            else:
                weight = 0
            total_weight += weight * item['quantity']
        return total_weight
    
    def get_total_savings(self):
        """
        Calculate total savings from discounts.
        """
        total_savings = 0
        for item in self:
            if item.get('product_obj'):
                original_price = item['product_obj'].price
                discounted_price = item['product_obj'].get_discounted_price()
                savings = original_price - discounted_price
            elif item.get('package_obj'):
                original_price = item['package_obj'].original_price
                discounted_price = item['package_obj'].price
                savings = original_price - discounted_price
            else:
                savings = 0
            total_savings += savings * item['quantity']
        return int(total_savings)
    
    def clear(self):
        """
        Remove all items from cart.
        """
        # پاک کردن از session
        if settings.CART_SESSION_ID in self.session:
            del self.session[settings.CART_SESSION_ID]
        
        # ریست کردن state داخلی
        self.cart = {}
        self.discount_code = None
        self.discount_percent = 0
        self.discount_amount = 0
        
        # ذخیره session خالی
        self.session[settings.CART_SESSION_ID] = {}
        self.session.modified = True
    
    def is_empty(self):
        """
        Check if cart is empty.
        """
        if not self.cart:
            return True
        
        item_count = sum(1 for item in self.cart.values() if isinstance(item, dict))
        return item_count == 0
    
    def apply_discount_code(self, code):
        """
        Apply discount code to cart.
        """
        try:
            discount_code = DiscountCode.objects.get(code=code, active=True)
        except DiscountCode.DoesNotExist:
            return False, "کد تخفیف نامعتبر است"
        
        if not discount_code.is_valid():
            return False, "کد تخفیف منقضی شده یا استفاده شده است"
        
        self.discount_code = code
        self.discount_percent = discount_code.percent
        self.discount_amount = discount_code.amount
        
        self.cart['discount_code'] = code
        self.cart['discount_percent'] = discount_code.percent
        self.cart['discount_amount'] = discount_code.amount
        
        self.save()
        return True, "کد تخفیف اعمال شد"
    
    def remove_discount_code(self):
        """
        Remove discount code from cart.
        """
        self.discount_code = None
        self.discount_percent = 0
        self.discount_amount = 0
        
        if 'discount_code' in self.cart:
            del self.cart['discount_code']
        if 'discount_percent' in self.cart:
            del self.cart['discount_percent']
        if 'discount_amount' in self.cart:
            del self.cart['discount_amount']
        
        self.save()
    
    def get_discounted_total(self):
        """
        Calculate total price after applying discount code.
        """
        total = self.get_total_price()
        
        if self.discount_code:
            try:
                discount_code = DiscountCode.objects.get(code=self.discount_code)
                if discount_code.is_valid():
                    if discount_code.amount > 0:
                        discount = min(discount_code.amount, total)
                        total -= discount
                    elif discount_code.percent > 0:
                        discount = int(total * discount_code.percent / 100)
                        total -= discount
            except DiscountCode.DoesNotExist:
                pass
        
        return int(total)