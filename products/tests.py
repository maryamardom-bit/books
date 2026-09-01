from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Product, Comment, Package, DiscountCode, FAQ, TieredDiscount
from .factories import (
    ProductFactory,
    PackageFactory,
    CommentFactory,
    DiscountCodeFactory,
    FAQFactory,
)


class ProductModelTest(TestCase):
    """Test Product model"""
    
    def setUp(self):
        self.product = ProductFactory(price=100000)
    
    def test_create_product(self):
        """Test creating product"""
        self.assertEqual(Product.objects.count(), 1)
        self.assertTrue(self.product.active)
        self.assertEqual(self.product.stock, self.product.available_stock)
    
    def test_discount_percent(self):
        """Test percentage discount"""
        self.product.discount_percent = 20
        self.product.save()
        
        self.assertTrue(self.product.is_on_sale())
        self.assertEqual(self.product.get_discounted_price(), 80000)
        self.assertEqual(self.product.get_savings(), 20000)
        self.assertEqual(self.product.get_discount_percent_display(), 20)
    
    def test_special_price(self):
        """Test special price"""
        self.product.special_price = 70000
        self.product.save()
        
        self.assertTrue(self.product.is_on_sale())
        self.assertEqual(self.product.get_discounted_price(), 70000)
        self.assertEqual(self.product.get_savings(), 30000)
    
    def test_no_discount(self):
        """Test no discount"""
        self.assertFalse(self.product.is_on_sale())
        self.assertEqual(self.product.get_discounted_price(), 100000)
        self.assertEqual(self.product.get_savings(), 0)
    
    def test_stock_management(self):
        """Test stock decrease/increase"""
        self.product.stock = 10
        self.product.save()
        
        # کاهش موجودی
        self.assertTrue(self.product.decrease_stock(3))
        self.assertEqual(self.product.stock, 7)
        
        # افزایش موجودی
        self.product.increase_stock(5)
        self.assertEqual(self.product.stock, 12)
    
    def test_reserved_stock(self):
        """Test reserved stock"""
        self.product.stock = 10
        self.product.save()
        
        # رزرو
        self.assertTrue(self.product.reserve_stock(4))
        self.assertEqual(self.product.reserved_stock, 4)
        self.assertEqual(self.product.available_stock, 6)
        
        # آزادسازی
        self.product.release_stock(2)
        self.assertEqual(self.product.reserved_stock, 2)
        self.assertEqual(self.product.available_stock, 8)


class ProductManagerTest(TestCase):
    """Test ProductManager"""
    
    def setUp(self):
        self.on_sale_product = ProductFactory(discount_percent=15)
        self.special_price_product = ProductFactory(special_price=50000)
        self.normal_product = ProductFactory(price=100000)
        self.inactive_product = ProductFactory(active=False, discount_percent=10)
    
    def test_get_on_sale_products(self):
        """Test filtering on-sale products"""
        on_sale = Product.objects.get_on_sale_products()
        
        self.assertIn(self.on_sale_product, on_sale)
        self.assertIn(self.special_price_product, on_sale)
        self.assertNotIn(self.normal_product, on_sale)
        self.assertNotIn(self.inactive_product, on_sale)
    
    def test_get_active_products(self):
        """Test filtering active products"""
        active = Product.objects.get_active_products()
        
        self.assertIn(self.on_sale_product, active)
        self.assertNotIn(self.inactive_product, active)


class PackageModelTest(TestCase):
    """Test Package model"""
    
    def setUp(self):
        self.product1 = ProductFactory(price=100000, weight=500)
        self.product2 = ProductFactory(price=200000, weight=300)
        
        # ساخت پکیج با محصولات
        self.package = PackageFactory(products=[self.product1, self.product2])
        
class DiscountCodeTest(TestCase):
    """Test DiscountCode model"""
    
    def setUp(self):
        self.code = DiscountCodeFactory(percent=20, max_uses=2)
    
    def test_is_valid(self):
        """Test code validity"""
        self.assertTrue(self.code.is_valid())
    
    def test_max_uses(self):
        """Test max uses limit"""
        self.code.used_count = 2
        self.code.save()
        
        self.assertFalse(self.code.is_valid())
    
    def test_apply_percent_discount(self):
        """Test percentage discount"""
        final_price, discount = self.code.apply_discount(100000)
        
        self.assertEqual(final_price, 80000)
        self.assertEqual(discount, 20000)
    
    def test_apply_amount_discount(self):
        """Test fixed amount discount"""
        self.code.percent = 0
        self.code.amount = 30000
        self.code.save()
        
        final_price, discount = self.code.apply_discount(100000)
        
        self.assertEqual(final_price, 70000)
        self.assertEqual(discount, 30000)


class CommentModelTest(TestCase):
    """Test Comment model"""
    
    def setUp(self):
        self.comment = CommentFactory()
    
    def test_create_comment(self):
        """Test creating comment"""
        self.assertFalse(self.comment.active)  # default should be False for approval
    
    def test_comment_relation(self):
        """Test comment relations"""
        self.assertIsNotNone(self.comment.product)
        self.assertIsNotNone(self.comment.author)


class FAQTest(TestCase):
    """Test FAQ model"""
    
    def setUp(self):
        self.faq = FAQFactory()
    
    def test_create_faq(self):
        """Test creating FAQ"""
        self.assertTrue(self.faq.is_active)
        self.assertIsNotNone(self.faq.question)
        self.assertIsNotNone(self.faq.answer)


class TieredDiscountTest(TestCase):
    """Test TieredDiscount model"""
    
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.tiered = TieredDiscount.objects.create(user=self.user)
    
    def test_initial_tier(self):
        """Test initial tier"""
        self.assertEqual(self.tiered.current_tier, 0)
        self.assertEqual(self.tiered.get_discount_percent(), 0)
    
    def test_advance_tier(self):
        """Test advancing tiers"""
        self.assertTrue(self.tiered.advance_tier())
        self.assertEqual(self.tiered.current_tier, 1)
        self.assertEqual(self.tiered.get_discount_percent(), 10)
        
        self.assertTrue(self.tiered.advance_tier())
        self.assertEqual(self.tiered.current_tier, 2)
        self.assertEqual(self.tiered.get_discount_percent(), 20)
        
        self.assertTrue(self.tiered.advance_tier())
        self.assertEqual(self.tiered.current_tier, 3)
        self.assertEqual(self.tiered.get_discount_percent(), 50)
        
        # Should not advance beyond 3
        self.assertFalse(self.tiered.advance_tier())
    
    def test_reset(self):
        """Test resetting tier"""
        self.tiered.advance_tier()
        self.tiered.reset()
        
        self.assertEqual(self.tiered.current_tier, 0)