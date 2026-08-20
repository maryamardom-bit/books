from django.utils.translation import gettext_lazy as _
from products.models import Product, Package


class Cart:
    def __init__(self, request):
        """
        initialize the cart
        """
        self.request = request
        self.session = request.session
        
        cart = self.session.get('cart')
        
        if not cart:
            cart = self.session['cart'] = {}
        
        self.cart = cart

    def add(self, obj, quantity=1, replace_current_quantity=False, is_package=False):
        """
        Add product or package to cart.
        
        Args:
            obj: Product or Package instance
            quantity: quantity to add
            replace_current_quantity: if True, replace quantity instead of adding
            is_package: if True, obj is Package, otherwise Product
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
        """
        Remove a product or package from the cart.
        """
        item_key = f"{'package' if is_package else 'product'}_{obj.id}"
        
        if item_key in self.cart:
            del self.cart[item_key]
            self.save()

    def save(self):
        """
        Mark session as modified to save changes
        """
        self.session.modified = True

    def __iter__(self):
        """
        Iterate over the items in the cart and get the products/packages
        from the database.
        """
        cart = self.cart.copy()
        
        # جدا کردن id های محصولات و پکیج‌ها
        product_ids = []
        package_ids = []
        
        for key in cart.keys():
            if key.startswith('product_'):
                product_ids.append(key.replace('product_', ''))
            elif key.startswith('package_'):
                package_ids.append(key.replace('package_', ''))
        
        # دریافت محصولات و پکیج‌ها از دیتابیس
        products = Product.objects.filter(id__in=product_ids)
        packages = Package.objects.filter(id__in=package_ids)
        
        # اضافه کردن اطلاعات محصولات
        for product in products:
            key = f'product_{product.id}'
            cart[key]['product_obj'] = product
            cart[key]['package_obj'] = None
            cart[key]['title'] = product.title
            cart[key]['price'] = product.get_discounted_price()
            cart[key]['original_price'] = product.price
            cart[key]['image'] = product.image
            cart[key]['weight'] = product.weight or 0
            cart[key]['is_package'] = False
        
        # اضافه کردن اطلاعات پکیج‌ها
        for package in packages:
            key = f'package_{package.id}'
            cart[key]['product_obj'] = None
            cart[key]['package_obj'] = package
            cart[key]['title'] = package.title
            cart[key]['price'] = package.price
            cart[key]['original_price'] = package.original_price
            cart[key]['image'] = package.image
            cart[key]['weight'] = package.get_total_weight()
            cart[key]['is_package'] = True
        
        # محاسبه قیمت کل برای هر آیتم
        for item in cart.values():
            item['total_price'] = item['price'] * item['quantity']
            yield item

    def __len__(self):
        """
        Count all items in the cart.
        """
        return sum(item['quantity'] for item in self.cart.values())

    def clear(self):
        """
        Remove cart from session
        """
        del self.session['cart']
        self.save()

    def get_total_price(self):
        """
        Calculate total price of all items in cart (with discount).
        """
        total = 0
        for item in self:
            total += item['total_price']
        return total

    def get_total_price_without_discount(self):
        """
        Calculate total price of all items in cart (without discount).
        """
        total = 0
        for item in self:
            total += item['original_price'] * item['quantity']
        return total

    def get_total_savings(self):
        """
        Calculate total savings (difference between original and discounted price).
        """
        return self.get_total_price_without_discount() - self.get_total_price()

    def get_total_weight(self):
        """
        Calculate total weight of all items in cart (grams).
        """
        total = 0
        for item in self:
            total += item['weight'] * item['quantity']
        return total

    def is_empty(self):
        """
        Check if cart is empty.
        """
        return len(self.cart) == 0