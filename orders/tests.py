from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.http import HttpRequest
from django.contrib.sessions.backends.db import SessionStore

from products.factories import ProductFactory, PackageFactory
from products.models import Product, Package
from .factories import OrderFactory, OrderItemFactory, ReturnRequestFactory
from .models import Order, OrderItem, ReturnRequest

# این را اضافه کنید
User = get_user_model()


class OrderModelTest(TestCase):
    """Test Order model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            phone_number='09123456789'
        )
        
        self.product1 = ProductFactory(price=100000, weight=500, stock=10)
        self.product2 = ProductFactory(price=150000, weight=700, stock=10)
        
        self.order = OrderFactory(
            user=self.user,
            total_price=0,
            total_weight=0
        )
        
        # ایجاد آیتم‌های سفارش
        self.item1 = OrderItemFactory(
            order=self.order,
            product=self.product1,
            quantity=2,
            price=self.product1.get_discounted_price()
        )
        
        self.item2 = OrderItemFactory(
            order=self.order,
            product=self.product2,
            quantity=1,
            price=self.product2.get_discounted_price()
        )
    
    def test_order_str(self):
        """Test order string representation"""
        self.assertEqual(str(self.order), f'Order {self.order.id}')
    
    def test_get_total_price(self):
        """Test calculating total price from items"""
        expected = (2 * self.product1.get_discounted_price()) + (1 * self.product2.get_discounted_price())
        self.assertEqual(self.order.get_total_price(), expected)
    
    def test_get_total_weight(self):
        """Test calculating total weight from items"""
        expected = (2 * 500) + (1 * 700)
        self.assertEqual(self.order.get_total_weight(), expected)
    
    def test_order_items_creation(self):
        """Test order items are created correctly"""
        self.assertEqual(self.order.items.count(), 2)
        self.assertEqual(self.item1.quantity, 2)
        self.assertEqual(self.item2.quantity, 1)
    
    def test_order_item_get_title(self):
        """Test getting item title"""
        self.assertEqual(self.item1.get_title(), self.product1.title)
        self.assertEqual(self.item1.get_weight(), 1000)  # 2 * 500
    
    def test_order_with_package_item(self):
        """Test order with package item"""
        package_product = ProductFactory(price=80000, weight=300, stock=10)
        package = PackageFactory(products=[package_product])
        
        package_item = OrderItemFactory(
            order=self.order,
            product=None,
            package=package,
            quantity=1,
            price=package.price
        )
        
        self.assertEqual(package_item.get_title(), package.title)
        self.assertEqual(package_item.get_weight(), 300)  # 1 * 300
    
    def test_order_user_relationship(self):
        """Test order belongs to user"""
        self.assertEqual(self.order.user, self.user)
        self.assertEqual(self.user.order_set.count(), 1)
    
    def test_order_is_paid_default(self):
        """Test default is_paid is True from factory"""
        self.assertTrue(self.order.is_paid)
    
    def test_order_payment_method_default(self):
        """Test default payment method"""
        self.assertEqual(self.order.payment_method, 'online')


class ReturnRequestModelTest(TestCase):
    """Test ReturnRequest model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='returnuser',
            password='testpass123'
        )
        
        self.order = OrderFactory(user=self.user)
        self.return_request = ReturnRequestFactory(
            order=self.order,
            user=self.user,
            status=ReturnRequest.ReturnStatus.PENDING
        )
    
    def test_return_request_str(self):
        """Test return request string representation"""
        self.assertEqual(
            str(self.return_request),
            f'Return #{self.return_request.id} - Order #{self.order.id}'
        )
    
    def test_can_request_return_within_3_days(self):
        """Test return request within 3 days of order"""
        # سفارش تازه ایجاد شده
        self.assertTrue(self.return_request.can_request_return())
    
    def test_can_request_return_after_3_days(self):
        """Test return request after 3 days of order"""
        # سفارش ۴ روز پیش
        self.order.datetime_created = timezone.now() - timezone.timedelta(days=4)
        self.order.save()
        
        self.assertFalse(self.return_request.can_request_return())
    
    def test_can_request_return_unpaid_order(self):
        """Test return request for unpaid order"""
        self.order.is_paid = False
        self.order.save()
        
        self.assertFalse(self.return_request.can_request_return())
    
    def test_return_request_status_choices(self):
        """Test return request status choices"""
        self.assertEqual(self.return_request.status, ReturnRequest.ReturnStatus.PENDING)
        
        # تغییر وضعیت
        self.return_request.status = ReturnRequest.ReturnStatus.APPROVED
        self.return_request.save()
        self.return_request.refresh_from_db()
        
        self.assertEqual(self.return_request.status, ReturnRequest.ReturnStatus.APPROVED)
    
    def test_return_request_order_relationship(self):
        """Test return request belongs to order and user"""
        self.assertEqual(self.return_request.order, self.order)
        self.assertEqual(self.return_request.user, self.user)
        self.assertEqual(self.order.return_requests.count(), 1)


class OrderCreateViewTest(TestCase):
    """Test order creation view"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='viewuser',
            password='testpass123',
            phone_number='09123456789'
        )
        self.client.login(username='viewuser', password='testpass123')
        
        self.product = ProductFactory(price=100000, weight=500, stock=10)
        
        # ساخت session با cart
        session = self.client.session
        session['cart'] = {
            str(self.product.id): {
                'quantity': 2,
                'price': str(self.product.get_discounted_price()),
                'item_type': 'product',
                'is_package': False,
                'title': self.product.title,
                'weight': str(self.product.weight or 0),
            }
        }
        session.save()
    
    def test_order_create_view_get(self):
        """Test GET request to order create page"""
        response = self.client.get(reverse('order:order_create'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/order_create.html')
    
    def test_order_create_view_post_success(self):
        """Test POST request to create order"""
        data = {
            'first_name': 'Test',
            'last_name': 'User',
            'phone_number': '09123456789',
            'address': 'Test Address',
            'order_notes': '',
            'payment-method': 'online',
        }
        
        response = self.client.post(reverse('order:order_create'), data)
        
        # باید به صفحه پرداخت redirect شود
        self.assertEqual(response.status_code, 302)
        
        # بررسی ایجاد سفارش
        order = Order.objects.filter(user=self.user).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.first_name, 'Test')
        self.assertEqual(order.last_name, 'User')
        self.assertEqual(order.total_price, 200000)  # 2 * 100000
        self.assertEqual(order.total_weight, 1000)  # 2 * 500
        
        # بررسی آیتم‌های سفارش
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 2)
        
        # بررسی کاهش موجودی
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)  # 10 - 2
        
        # بررسی خالی شدن سبد
        self.assertEqual(self.client.session.get('cart'), {})
    
    def test_order_create_view_empty_cart(self):
        """Test order create with empty cart"""
        # خالی کردن سبد
        session = self.client.session
        session['cart'] = {}
        session.save()
        
        response = self.client.get(reverse('order:order_create'))
        
        # باید به لیست محصولات redirect شود
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('product:product_list'))
    
    def test_order_create_view_installment(self):
        """Test order creation with installment payment"""
        data = {
            'first_name': 'Test',
            'last_name': 'User',
            'phone_number': '09123456789',
            'address': 'Test Address',
            'order_notes': '',
            'payment-method': 'installment',
            'installment_plan_id': 'plan_123',
        }
        
        response = self.client.post(reverse('order:order_create'), data)
        
        self.assertEqual(response.status_code, 302)
        
        order = Order.objects.filter(user=self.user).first()
        self.assertEqual(order.payment_method, 'installment')
        self.assertEqual(order.installment_plan_id, 'plan_123')


class RequestReturnViewTest(TestCase):
    """Test return request view"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='returnviewuser',
            password='testpass123'
        )
        self.client.login(username='returnviewuser', password='testpass123')
        
        self.order = OrderFactory(user=self.user, is_paid=True)
    
    def test_request_return_view_get(self):
        """Test GET request to return page"""
        response = self.client.get(reverse('order:request_return', args=[self.order.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/request_return.html')
    
    def test_request_return_view_post_success(self):
        """Test POST request to submit return"""
        data = {
            'reason': 'Product is damaged',
        }
        
        response = self.client.post(
            reverse('order:request_return', args=[self.order.id]),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        
        # بررسی ایجاد درخواست برگشت
        return_request = ReturnRequest.objects.filter(
            order=self.order,
            user=self.user
        ).first()
        
        self.assertIsNotNone(return_request)
        self.assertEqual(return_request.reason, 'Product is damaged')
        self.assertEqual(return_request.status, ReturnRequest.ReturnStatus.PENDING)
    
    def test_request_return_view_unpaid_order(self):
        """Test return request for unpaid order"""
        self.order.is_paid = False
        self.order.save()
        
        response = self.client.get(reverse('order:request_return', args=[self.order.id]))
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ReturnRequest.objects.filter(order=self.order, user=self.user).count(),
            0
        )
    
    def test_request_return_view_expired(self):
        """Test return request after 3 days"""
        self.order.datetime_created = timezone.now() - timezone.timedelta(days=4)
        self.order.save()
        
        response = self.client.get(reverse('order:request_return', args=[self.order.id]))
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ReturnRequest.objects.filter(order=self.order, user=self.user).count(),
            0
        )
    
    def test_request_return_duplicate(self):
        """Test duplicate return request"""
        # ایجاد اولین درخواست
        ReturnRequestFactory(
            order=self.order,
            user=self.user,
            status=ReturnRequest.ReturnStatus.PENDING
        )
        
        response = self.client.get(reverse('order:request_return', args=[self.order.id]))
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ReturnRequest.objects.filter(order=self.order, user=self.user).count(),
            1  # فقط یک درخواست
        )


class MyReturnsViewTest(TestCase):
    """Test my returns view"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='myreturnsuser',
            password='testpass123'
        )
        self.client.login(username='myreturnsuser', password='testpass123')
        
        self.order = OrderFactory(user=self.user)
        self.return_request = ReturnRequestFactory(
            order=self.order,
            user=self.user,
            status=ReturnRequest.ReturnStatus.PENDING
        )
    
    def test_my_returns_view(self):
        """Test viewing my returns"""
        response = self.client.get(reverse('order:my_returns'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/my_returns.html')
        self.assertContains(response, self.return_request.reason)