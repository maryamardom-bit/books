# cart/cart.py
from django.conf import settings
from django.utils.translation import gettext as _
from products.models import Product, Package, DiscountCode


class Cart:
    def __init__(self, request):
        """
        Initialize the cart.
        """
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart
        self.discount_code = self.cart.get('discount_code')
        self.discount_percent = self.cart.get('discount_percent', 0)
        self.discount_amount = self.cart.get('discount_amount', 0)
    
    def _extract_item_id(self, item_id_str):
        """
        Extract numeric ID from item key.
        Handles both '1' and 'product_1' formats.
        """
        try:
            return int(item_id_str)
        except (ValueError, TypeError):
            parts = str(item_id_str).split('_')
            if len(parts) == 2 and parts[1].isdigit():
                return int(parts[1])
            return None
    
    def _stock_limit(self, item, is_package):
        if is_package:
            return int(item.stock or 0)
        return int(item.available_stock or 0)

    def add(self, item, quantity=1, replace_current_quantity=False, is_package=False):
        """
        Add a product or package to the cart or update its quantity.

        Returns 'ok', 'limited' when the request was cut to available stock,
        or 'out_of_stock' when nothing could be added.
        """
        item_type = 'package' if is_package else 'product'
        item_id = f'{item_type}_{item.id}'
        if not getattr(item, 'active', True):
            return 'out_of_stock'
        limit = self._stock_limit(item, is_package)

        existing = self.cart.get(item_id)
        current = int(existing.get('quantity') or 0) if isinstance(existing, dict) else 0
        requested = quantity if replace_current_quantity else current + quantity
        if limit <= 0 or requested <= 0:
            return 'out_of_stock'

        status = 'limited' if requested > limit else 'ok'
        requested = min(requested, limit)

        if is_package:
            weight = item.get_total_weight()
        else:
            weight = item.weight if item.weight else 0

        if not isinstance(existing, dict):
            self.cart[item_id] = {
                'quantity': requested,
                'price': str(item.price),
                'item_type': item_type,
                'is_package': is_package,
                'title': item.title,
                'weight': str(weight),
            }
        else:
            existing['quantity'] = requested

        self.save()
        return status

    def decrease(self, item, quantity=1, is_package=False):
        """
        Remove one or more of an item. Returns 'decreased', 'removed', or 'missing'.
        """
        item_type = 'package' if is_package else 'product'
        item_id = f'{item_type}_{item.id}'
        entry = self.cart.get(item_id)
        if not isinstance(entry, dict) or not entry.get('quantity'):
            return 'missing'

        entry['quantity'] = int(entry['quantity']) - quantity
        if entry['quantity'] <= 0:
            del self.cart[item_id]
            self.save()
            return 'removed'

        self.save()
        return 'decreased'
    
    def save(self):
        self.session[settings.CART_SESSION_ID] = self.cart
        self.session.modified = True
    
    def remove(self, item, is_package=False):
        item_type = 'package' if is_package else 'product'
        item_id = f'{item_type}_{item.id}'
        
        if item_id in self.cart:
            del self.cart[item_id]
            self.save()
    
    def __iter__(self):
        cart_items = self.cart.copy()
        
        product_ids = []
        package_ids = []
        
        for item_id, item_data in cart_items.items():
            if not isinstance(item_data, dict):
                continue
            
            item_id_int = self._extract_item_id(item_id)
            if item_id_int is None:
                continue
            
            if item_data.get('item_type') == 'package':
                package_ids.append(item_id_int)
            else:
                product_ids.append(item_id_int)
        
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
        packages = {p.id: p for p in Package.objects.filter(id__in=package_ids)}
        
        for item_id, item_data in cart_items.items():
            if not isinstance(item_data, dict):
                continue
            
            item_id_int = self._extract_item_id(item_id)
            if item_id_int is None:
                continue
            
            quantity = item_data['quantity']
            is_package = item_data.get('item_type') == 'package'
            result = {
                'key': item_id,
                'quantity': quantity,
                'title': item_data.get('title', ''),
                'is_package': is_package,
                'item_type': item_data.get('item_type', 'product'),
                'author': '',
            }

            if is_package:
                package = packages.get(item_id_int)
                if not package:
                    continue
                result['package_obj'] = package
                result['title'] = package.title
                result['price'] = package.price
                result['original_price'] = package.original_price
                result['total_price'] = package.price * quantity
                result['image'] = package.image
                result['stock_limit'] = int(package.stock or 0)
            else:
                product = products.get(item_id_int)
                if not product:
                    continue
                discounted = product.get_discounted_price()
                result['product_obj'] = product
                result['title'] = product.title
                result['author'] = product.author
                result['price'] = discounted
                result['original_price'] = product.price
                result['total_price'] = discounted * quantity
                result['image'] = product.image
                result['stock_limit'] = int(product.available_stock or 0)

            yield result
    
    def __len__(self):
        return sum(
            item['quantity'] 
            for item_id, item in self.cart.items() 
            if isinstance(item, dict) and item.get('quantity')
        )
    
    def get_total_price(self):
        total = 0
        for item in self:
            total += int(item['total_price'])
        return total
    
    def get_total_weight(self):
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
        return total_savings
    
    def reconcile(self):
        """
        Drop items that are gone or out of stock, and cap quantities to stock.
        Returns human-readable notes for the shopper.
        """
        notes = []
        product_ids = []
        package_ids = []
        rows = []

        for key, data in list(self.cart.items()):
            if not isinstance(data, dict) or 'item_type' not in data:
                continue
            item_id = self._extract_item_id(key)
            if item_id is None:
                del self.cart[key]
                continue
            rows.append((key, data, item_id))
            if data.get('item_type') == 'package':
                package_ids.append(item_id)
            else:
                product_ids.append(item_id)

        products = {
            product.id: product
            for product in Product.objects.filter(id__in=product_ids, active=True)
        }
        packages = {
            package.id: package
            for package in Package.objects.filter(id__in=package_ids, active=True)
        }
        changed = False

        for key, data, item_id in rows:
            if data.get('item_type') == 'package':
                obj = packages.get(item_id)
                limit = int(obj.stock or 0) if obj else 0
            else:
                obj = products.get(item_id)
                limit = int(obj.available_stock or 0) if obj else 0
            title = obj.title if obj else data.get('title', '')
            quantity = int(data.get('quantity') or 0)

            if obj is None or limit <= 0:
                del self.cart[key]
                changed = True
                notes.append(
                    _('“%(title)s” was removed because it is no longer available.')
                    % {'title': title}
                )
                continue

            if quantity > limit:
                data['quantity'] = limit
                changed = True
                notes.append(
                    _('Quantity of “%(title)s” was reduced to the available stock.')
                    % {'title': title}
                )

        if changed:
            self.save()
        return notes

    def clear(self):
        if settings.CART_SESSION_ID in self.session:
            del self.session[settings.CART_SESSION_ID]
        
        self.cart = {}
        self.discount_code = None
        self.discount_percent = 0
        self.discount_amount = 0
        
        self.session[settings.CART_SESSION_ID] = {}
        self.session.modified = True
    
    def is_empty(self):
        if not self.cart:
            return True
        
        item_count = sum(
            1 
            for item in self.cart.values() 
            if isinstance(item, dict) and 'item_type' in item
        )
        return item_count == 0
    
    def apply_discount_code(self, code):
        try:
            discount_code = DiscountCode.objects.get(code=code, active=True)
        except DiscountCode.DoesNotExist:
            return False, _("Invalid discount code")
        
        if not discount_code.is_valid():
            return False, _("This discount code has expired or already been used")
        
        self.discount_code = code
        self.discount_percent = discount_code.percent
        self.discount_amount = discount_code.amount
        
        self.cart['discount_code'] = code
        self.cart['discount_percent'] = discount_code.percent
        self.cart['discount_amount'] = discount_code.amount
        
        self.save()
        return True, _("Discount code applied")
    
    def remove_discount_code(self):
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
        
        return total