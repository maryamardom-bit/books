from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from products.factories import ProductFactory, PackageFactory, FAQFactory, CommentFactory
from products.models import Product, Package, Comment, FAQ

User = get_user_model()


class ProductAPITest(APITestCase):
    """Test Product API"""
    
    def setUp(self):
        self.client = APIClient()
        self.product1 = ProductFactory(price=100000, discount_percent=10)
        self.product2 = ProductFactory(price=200000)
    
    def test_list_products(self):
        """Test listing products"""
        response = self.client.get('/api/products/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_product_detail(self):
        """Test product detail"""
        response = self.client.get(f'/api/products/{self.product1.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], self.product1.title)
        self.assertEqual(response.data['discounted_price'], 90000)  # 100000 - 10%
    
    def test_filter_by_category(self):
        """Test filtering by category"""
        response = self.client.get(f'/api/products/?category={self.product1.category}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_filter_on_sale(self):
        """Test filtering on sale products"""
        response = self.client.get('/api/products/?on_sale=true')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # فقط محصول تخفیف‌دار باید برگردد
        self.assertTrue(all(p['is_on_sale'] for p in response.data['results']))
    
    def test_search_products(self):
        """Test searching products"""
        response = self.client.get(f'/api/products/?search={self.product1.title[:5]}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PackageAPITest(APITestCase):
    """Test Package API"""
    
    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(price=100000)
        self.package = PackageFactory(products=[self.product])
    
    def test_list_packages(self):
        """Test listing packages"""
        response = self.client.get('/api/packages/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
    
    def test_package_detail(self):
        """Test package detail"""
        response = self.client.get(f'/api/packages/{self.package.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], self.package.title)
        self.assertEqual(response.data['price'], self.package.price)


class FAQAPITest(APITestCase):
    """Test FAQ API"""
    
    def setUp(self):
        self.client = APIClient()
        self.faq = FAQFactory(question='سوال تستی', answer='پاسخ تستی')
    
    def test_list_faqs(self):
        """Test listing FAQs"""
        response = self.client.get('/api/faqs/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['question'], 'سوال تستی')


class CommentAPITest(APITestCase):
    """Test Comment API"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='commentuser',
            password='testpass123'
        )
        self.product = ProductFactory()
        
        # Login
        self.client.login(username='commentuser', password='testpass123')
    
    def test_create_comment(self):
        """Test creating comment"""
        data = {
            'product': self.product.id,
            'body': 'کتاب عالی بود',
            'stars': 5,
        }
        
        response = self.client.post('/api/comments/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['body'], 'کتاب عالی بود')
        self.assertEqual(response.data['author_name'], 'commentuser')
    
    def test_list_comments(self):
        """Test listing comments"""
        CommentFactory(
            product=self.product,
            author=self.user,
            body='نظر تستی',
            stars=4,
            active=True
        )
        
        response = self.client.get(f'/api/comments/?product={self.product.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CartAPITest(APITestCase):
    """Test Cart API"""
    
    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(price=100000, stock=10)
    
    def test_get_empty_cart(self):
        """Test getting empty cart"""
        response = self.client.get('/api/cart/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['items'], [])
        self.assertEqual(response.data['total_price'], 0)
    
    def test_add_to_cart(self):
        """Test adding product to cart"""
        data = {
            'item_id': self.product.id,
            'quantity': 2,
            'is_package': False,
        }
        
        response = self.client.post('/api/cart/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['cart_count'], 2)
        self.assertEqual(response.data['total_price'], 200000)
    
    def test_remove_from_cart(self):
        """Test removing product from cart"""
        # اول اضافه کن
        self.client.post('/api/cart/', {
            'item_id': self.product.id,
            'quantity': 1,
            'is_package': False,
        }, format='json')
        
        # بعد حذف کن
        data = {
            'item_id': self.product.id,
            'is_package': False,
        }
        
        response = self.client.delete('/api/cart/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['cart_count'], 0)


class ProfileAPITest(APITestCase):
    """Test Profile API"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='profileuser',
            password='testpass123',
            first_name='علی',
            last_name='محمدی'
        )
        
        self.client.login(username='profileuser', password='testpass123')
    
    def test_get_profile(self):
        """Test getting profile"""
        response = self.client.get('/api/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'profileuser')
        self.assertEqual(response.data['first_name'], 'علی')
    
    def test_update_profile(self):
        """Test updating profile"""
        data = {
            'first_name': 'حسین',
            'last_name': 'رضایی',
        }
        
        response = self.client.put('/api/profile/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'حسین')
        self.assertEqual(response.data['last_name'], 'رضایی')
    
    def test_profile_requires_auth(self):
        """Test profile requires authentication"""
        # خروج از سیستم
        self.client.logout()
        
        response = self.client.get('/api/profile/')
        
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])