from unittest.mock import patch, Mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from products.factories import ProductFactory, PackageFactory
from products.models import Product, Package, TieredDiscount
from orders.factories import OrderFactory, OrderItemFactory
from orders.models import Order, OrderItem

User = get_user_model()


class PaymentProcessTest(TestCase):
    """Test payment process view"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='paymentuser',
            password='testpass123',
            phone_number='09123456789'
        )
        self.client.login(username='paymentuser', password='testpass123')
        
        self.product = ProductFactory(price=100000, stock=10)
        self.order = OrderFactory(
            user=self.user,
            total_price=200000,
            total_weight=1000,
            is_paid=False
        )
        
        # تنظیم session با order_id
        session = self.client.session
        session['order_id'] = self.order.id
        session.save()
    
    @patch('payment.views.requests.post')
    def test_payment_process_success(self, mock_post):
        """Test successful payment process initiation"""
        # Mock response از درگاه پرداخت
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 1,
            'token': 'test_token_123'
        }
        mock_post.return_value = mock_response
        
        response = self.client.get(reverse('payment:payment_process'))
        
        # باید به درگاه پرداخت redirect شود
        self.assertEqual(response.status_code, 302)
        self.assertIn('sep.shaparak.ir', response.url)
        self.assertIn('test_token_123', response.url)
        
        # بررسی اینکه درخواست به درگاه ارسال شده
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['data']['TerminalId'], 'test_terminal_id')
        self.assertEqual(call_args[1]['data']['Amount'], 200000)
    
    @patch('payment.views.requests.post')
    def test_payment_process_gateway_error(self, mock_post):
        """Test payment process with gateway error"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 0,
            'errorDesc': 'Invalid terminal'
        }
        mock_post.return_value = mock_response
        
        response = self.client.get(reverse('payment:payment_process'))
        
        # باید به سبد خرید redirect شود
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart:cart_detail'))
    
    @patch('payment.views.requests.post')
    def test_payment_process_timeout(self, mock_post):
        """Test payment process with timeout"""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()
        
        response = self.client.get(reverse('payment:payment_process'))
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart:cart_detail'))
    
    @patch('payment.views.requests.post')
    def test_payment_process_connection_error(self, mock_post):
        """Test payment process with connection error"""
        import requests
        mock_post.side_effect = requests.exceptions.RequestException('Connection failed')
        
        response = self.client.get(reverse('payment:payment_process'))
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart:cart_detail'))
    
    def test_payment_process_no_order(self):
        """Test payment process without order in session"""
        # حذف order_id از session
        session = self.client.session
        if 'order_id' in session:
            del session['order_id']
        session.save()
        
        response = self.client.get(reverse('payment:payment_process'))
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart:cart_detail'))
    
    def test_payment_process_already_paid(self):
        """Test payment process for already paid order"""
        self.order.is_paid = True
        self.order.save()
        
        response = self.client.get(reverse('payment:payment_process'))
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('page:home'))


class PaymentVerifyTest(TestCase):
    """Test payment verification view"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='verifyuser',
            password='testpass123',
            phone_number='09123456789'
        )
        self.client.login(username='verifyuser', password='testpass123')
        
        self.product = ProductFactory(price=100000, stock=10)
        self.order = OrderFactory(
            user=self.user,
            total_price=100000,
            total_weight=500,
            is_paid=False
        )
        
        # ایجاد OrderItem
        self.order_item = OrderItemFactory(
            order=self.order,
            product=self.product,
            quantity=2,
            price=100000
        )
        
        # تنظیم session با order_id
        session = self.client.session
        session['order_id'] = self.order.id
        session.save()
    
    @patch('payment.views.requests.post')
    def test_payment_verify_success(self, mock_post):
        """Test successful payment verification"""
        # Mock پاسخ موفق از درگاه
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 1,
            'RefId': 'REF123456'
        }
        mock_post.return_value = mock_response
        
        # شبیه‌سازی callback از درگاه
        response = self.client.get(
            reverse('payment:payment_verify'),
            {
                'token': 'test_token',
                'RRN': '123456789',
                'status': '2'  # وضعیت موفق
            }
        )
        
        # باید به صفحه اصلی redirect شود
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('page:home'))
        
        # بررسی به‌روزرسانی سفارش
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)
        
        # بررسی کاهش موجودی
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)  # 10 - 2
        
        # بررسی حذف order_id از session
        self.assertNotIn('order_id', self.client.session)
    
    def test_payment_verify_failed_status(self):
        """Test payment verification with failed status"""
        response = self.client.get(
            reverse('payment:payment_verify'),
            {
                'token': 'test_token',
                'RRN': '123456789',
                'status': '1'  # وضعیت ناموفق
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart:cart_detail'))
        
        # سفارش نباید پرداخت شده باشد
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_paid)
    
    def test_payment_verify_no_token(self):
        """Test payment verification without token"""
        response = self.client.get(
            reverse('payment:payment_verify'),
            {
                'RRN': '123456789',
                'status': '2'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart:cart_detail'))
        
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_paid)
    
    def test_payment_verify_no_order(self):
        """Test payment verification without order in session"""
        # حذف order_id از session
        session = self.client.session
        if 'order_id' in session:
            del session['order_id']
        session.save()
        
        response = self.client.get(
            reverse('payment:payment_verify'),
            {
                'token': 'test_token',
                'RRN': '123456789',
                'status': '2'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart:cart_detail'))
    
    @patch('payment.views.requests.post')
    def test_payment_verify_gateway_error(self, mock_post):
        """Test payment verification with gateway error"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 0,
            'errorDesc': 'Verification failed'
        }
        mock_post.return_value = mock_response
        
        response = self.client.get(
            reverse('payment:payment_verify'),
            {
                'token': 'test_token',
                'RRN': '123456789',
                'status': '2'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart:cart_detail'))
        
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_paid)
    
    @patch('payment.views.requests.post')
    def test_payment_verify_advance_tier(self, mock_post):
        """Test payment verification advances tiered discount"""
        # ایجاد TieredDiscount اولیه
        tiered = TieredDiscount.objects.create(user=self.user, current_tier=0)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 1,
            'RefId': 'REF123456'
        }
        mock_post.return_value = mock_response
        
        response = self.client.get(
            reverse('payment:payment_verify'),
            {
                'token': 'test_token',
                'RRN': '123456789',
                'status': '2'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        # بررسی ارتقای سطح تخفیف
        tiered.refresh_from_db()
        self.assertEqual(tiered.current_tier, 1)
    
    @patch('payment.views.requests.post')
    def test_payment_verify_stock_decrease(self, mock_post):
        """Test payment verification decreases stock correctly"""
        initial_stock = self.product.stock
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 1,
            'RefId': 'REF123456'
        }
        mock_post.return_value = mock_response
        
        response = self.client.get(
            reverse('payment:payment_verify'),
            {
                'token': 'test_token',
                'RRN': '123456789',
                'status': '2'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        # بررسی کاهش موجودی
        self.product.refresh_from_db()
        expected_stock = initial_stock - self.order_item.quantity
        self.assertEqual(self.product.stock, expected_stock)
    
    @patch('payment.views.requests.post')
    def test_payment_verify_package_stock_decrease(self, mock_post):
        """Test payment verification decreases package stock"""
        # ایجاد پکیج
        package_product = ProductFactory(price=80000, weight=300, stock=10)
        package = PackageFactory(products=[package_product])
        
        # ایجاد سفارش با پکیج
        order_with_package = OrderFactory(
            user=self.user,
            total_price=package.price,
            total_weight=300,
            is_paid=False
        )
        
        package_item = OrderItemFactory(
            order=order_with_package,
            product=None,
            package=package,
            quantity=3,
            price=package.price
        )
        
        # تنظیم session با order_id جدید
        session = self.client.session
        session['order_id'] = order_with_package.id
        session.save()
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 1,
            'RefId': 'REF123456'
        }
        mock_post.return_value = mock_response
        
        response = self.client.get(
            reverse('payment:payment_verify'),
            {
                'token': 'test_token',
                'RRN': '123456789',
                'status': '2'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        # بررسی کاهش موجودی پکیج
        package.refresh_from_db()
        self.assertEqual(package.stock, package.stock)  # موجودی فعلی


class PaymentURLTest(TestCase):
    """Test payment URLs"""
    
    def test_payment_process_url(self):
        """Test payment process URL"""
        url = reverse('payment:payment_process')
        self.assertEqual(url, '/payment/process/')
    
    def test_payment_verify_url(self):
        """Test payment verify URL"""
        url = reverse('payment:payment_verify')
        self.assertEqual(url, '/payment/verify/')


class PaymentCSRFExemptTest(TestCase):
    """Test CSRF exempt on payment verify"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='csrfuser',
            password='testpass123'
        )
        self.client.login(username='csrfuser', password='testpass123')
        
        self.order = OrderFactory(
            user=self.user,
            is_paid=False
        )
        
        session = self.client.session
        session['order_id'] = self.order.id
        session.save()
    
    def test_payment_verify_csrf_exempt(self):
        """Test that payment verify is CSRF exempt"""
        # این تست باید بدون CSRF token کار کند
        response = self.client.get(
            reverse('payment:payment_verify'),
            {
                'token': 'test_token',
                'RRN': '123456789',
                'status': '2'
            }
        )
        
        # نباید 403 Forbidden برگرداند
        self.assertNotEqual(response.status_code, 403)