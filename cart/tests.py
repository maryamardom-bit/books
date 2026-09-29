# cart/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.contrib.sessions.backends.db import SessionStore
from django.urls import reverse

from products.factories import ProductFactory, PackageFactory, DiscountCodeFactory
from .cart import Cart


class CartTest(TestCase):
    """Test Cart functionality"""
    
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        
        self.product = ProductFactory(price=100000, stock=100, reserved_stock=0)
        
        # ساخت پکیج با محصول
        product_for_package = ProductFactory(price=150000, stock=100)
        self.package = PackageFactory(products=[product_for_package], stock=50)
        self.package.refresh_from_db()
        
        # ساخت request با session
        self.request = HttpRequest()
        self.request.user = self.user
        self.request.session = SessionStore()
        self.request.session.create()
    
    def test_add_product(self):
        """Test adding product to cart"""
        cart = Cart(self.request)
        cart.add(self.product, quantity=2, is_package=False)
        
        self.assertEqual(len(cart), 2)
        self.assertFalse(cart.is_empty())
    
    def test_add_package(self):
        """Test adding package to cart"""
        cart = Cart(self.request)
        cart.add(self.package, quantity=1, is_package=True)
        
        self.assertEqual(len(cart), 1)
        # بررسی قیمت پکیج
        self.assertEqual(self.package.price, 150000)
        self.assertEqual(self.package.original_price, 150000)
    
    def test_decrease_product(self):
        """Test decreasing quantity, including removal of the last copy."""
        cart = Cart(self.request)
        cart.add(self.product, quantity=2, is_package=False)

        self.assertEqual(cart.decrease(self.product, is_package=False), 'decreased')
        self.assertEqual(len(cart), 1)
        self.assertEqual(cart.decrease(self.product, is_package=False), 'removed')
        self.assertEqual(len(cart), 0)
        self.assertEqual(cart.decrease(self.product, is_package=False), 'missing')

    def test_remove_product(self):
        """Test removing product from cart"""
        cart = Cart(self.request)
        cart.add(self.product, quantity=2, is_package=False)
        cart.remove(self.product, is_package=False)
        
        self.assertEqual(len(cart), 0)
        self.assertTrue(cart.is_empty())
    
    def test_iteration_includes_cover_image(self):
        """Cart rows expose the book or package cover for the cart page."""
        cart = Cart(self.request)
        cart.add(self.product, quantity=1, is_package=False)
        cart.add(self.package, quantity=1, is_package=True)

        items = {item['title']: item for item in cart}
        product_row = items[self.product.title]
        package_row = items[self.package.title]

        self.assertEqual(product_row['image'], self.product.image)
        self.assertEqual(package_row['image'], self.package.image)
        self.assertEqual(product_row['original_price'], self.product.price)

    def test_replace_quantity(self):
        """Test replacing quantity"""
        cart = Cart(self.request)
        cart.add(self.product, quantity=3, is_package=False)
        cart.add(self.product, quantity=5, replace_current_quantity=True, is_package=False)
        
        items = list(cart)
        self.assertEqual(items[0]['quantity'], 5)
    
    def test_get_total_price(self):
        """Test total price calculation"""
        cart = Cart(self.request)
        cart.add(self.product, quantity=2, is_package=False)
        
        expected = 200000
        self.assertEqual(cart.get_total_price(), expected)
    
    def test_get_total_price_with_discount(self):
        """Test total price with discount"""
        self.product.discount_percent = 20
        self.product.save()
        
        cart = Cart(self.request)
        cart.add(self.product, quantity=2, is_package=False)
        
        expected = 160000
        self.assertEqual(cart.get_total_price(), expected)
    
    def test_get_total_weight(self):
        """Test total weight calculation"""
        self.product.weight = 500
        self.product.save()
        
        cart = Cart(self.request)
        cart.add(self.product, quantity=3, is_package=False)
        
        expected = 1500
        self.assertEqual(cart.get_total_weight(), expected)
    
    def test_get_total_savings(self):
        """Test total savings"""
        self.product.discount_percent = 25
        self.product.save()
        
        cart = Cart(self.request)
        cart.add(self.product, quantity=2, is_package=False)
        
        expected = 50000
        self.assertEqual(cart.get_total_savings(), expected)
    
    def test_clear_cart(self):
        """Test clearing cart"""
        cart = Cart(self.request)
        cart.add(self.product, quantity=2, is_package=False)
        cart.clear()
        
        self.assertTrue(cart.is_empty())
        self.assertEqual(len(cart), 0)
    
    def test_apply_discount_code(self):
        """Test applying discount code"""
        discount_code = DiscountCodeFactory(percent=10)
        
        cart = Cart(self.request)
        cart.add(self.product, quantity=1, is_package=False)
        
        success, message = cart.apply_discount_code(discount_code.code)
        
        self.assertTrue(success)
        self.assertEqual(cart.discount_percent, 10)
        self.assertEqual(cart.get_discounted_total(), 90000)
    
    def test_remove_discount_code(self):
        """Test removing discount code"""
        discount_code = DiscountCodeFactory(percent=10)
        
        cart = Cart(self.request)
        cart.add(self.product, quantity=1, is_package=False)
        cart.apply_discount_code(discount_code.code)
        cart.remove_discount_code()
        
        self.assertIsNone(cart.discount_code)
        self.assertEqual(cart.discount_percent, 0)
    
    def test_mixed_cart(self):
        """Test cart with both product and package"""
        cart = Cart(self.request)
        cart.add(self.product, quantity=2, is_package=False)
        cart.add(self.package, quantity=1, is_package=True)
        
        # ۲ محصول + ۱ پکیج = ۳ آیتم
        self.assertEqual(len(cart), 3)
    
    def test_is_empty(self):
        """Test is_empty method"""
        cart = Cart(self.request)
        self.assertTrue(cart.is_empty())
        
        cart.add(self.product, quantity=1, is_package=False)
        self.assertFalse(cart.is_empty())

    def test_add_caps_quantity_at_stock(self):
        self.product.stock = 2
        self.product.save()
        cart = Cart(self.request)
        status = cart.add(self.product, quantity=5, is_package=False)
        self.assertEqual(status, 'limited')
        self.assertEqual(list(cart)[0]['quantity'], 2)

    def test_add_out_of_stock_does_not_insert(self):
        self.product.stock = 0
        self.product.save()
        cart = Cart(self.request)
        status = cart.add(self.product, quantity=1, is_package=False)
        self.assertEqual(status, 'out_of_stock')
        self.assertTrue(cart.is_empty())

    def test_reconcile_drops_unavailable_title(self):
        cart = Cart(self.request)
        cart.add(self.product, quantity=1, is_package=False)
        self.product.active = False
        self.product.save()
        notes = cart.reconcile()
        self.assertTrue(cart.is_empty())
        self.assertEqual(len(notes), 1)


class CartDecreaseViewTest(TestCase):
    def setUp(self):
        self.product = ProductFactory(price=100000)

    def _seed_cart(self, quantity):
        session = self.client.session
        session['cart'] = {
            f'product_{self.product.id}': {
                'quantity': quantity,
                'price': '100000',
                'item_type': 'product',
                'is_package': False,
                'title': self.product.title,
                'weight': '0',
            }
        }
        session.save()

    def test_minus_removes_the_last_copy(self):
        self._seed_cart(1)
        response = self.client.post(
            reverse('cart:cart_decrease', args=[self.product.id]),
            HTTP_REFERER='/cart/',
        )
        self.assertEqual(response.status_code, 302)
        cart = self.client.session.get('cart', {})
        self.assertNotIn(f'product_{self.product.id}', cart)

    def test_cart_page_minus_stays_enabled_at_one(self):
        self._seed_cart(1)
        response = self.client.get(reverse('cart:cart_detail'))
        html = response.content.decode()
        decrease_url = reverse('cart:cart_decrease', args=[self.product.id])
        self.assertIn(decrease_url, html)
        button = html.split(decrease_url, 1)[1].split('</form>', 1)[0]
        self.assertNotIn('disabled', button)

    def test_remove_requires_post(self):
        self._seed_cart(1)
        response = self.client.get(reverse('cart:cart_remove', args=[self.product.id]))
        self.assertEqual(response.status_code, 405)
        self.assertIn(f'product_{self.product.id}', self.client.session.get('cart', {}))

    def test_anonymous_cart_asks_for_login(self):
        self.product.author = 'کسری'
        self.product.stock = 8
        self.product.save()
        self._seed_cart(1)
        response = self.client.get(reverse('cart:cart_detail'))
        self.assertContains(response, reverse('account_login'))
        self.assertContains(response, 'کسری')
        self.assertNotContains(response, 'Total Weight')
        self.assertContains(response, 'ادامه خرید')

    def test_empty_discount_code_is_rejected(self):
        response = self.client.post(reverse('cart:apply_discount'), {'code': '   '}, follow=True)
        self.assertContains(response, 'کد تخفیف را وارد کنید.')