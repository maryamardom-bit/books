# cart/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.contrib.sessions.backends.db import SessionStore

from products.factories import ProductFactory, PackageFactory, DiscountCodeFactory
from .cart import Cart


class CartTest(TestCase):
    """Test Cart functionality"""
    
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        
        self.product = ProductFactory(price=100000)
        
        # ساخت پکیج با محصول
        product_for_package = ProductFactory(price=150000)
        self.package = PackageFactory(products=[product_for_package])
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
    
    def test_remove_product(self):
        """Test removing product from cart"""
        cart = Cart(self.request)
        cart.add(self.product, quantity=2, is_package=False)
        cart.remove(self.product, is_package=False)
        
        self.assertEqual(len(cart), 0)
        self.assertTrue(cart.is_empty())
    
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