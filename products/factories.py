import factory
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Product, Comment, Package, ProductBlog, FAQ, DiscountCode, InstallmentPlan


class ProductFactory(factory.django.DjangoModelFactory):
    """Factory for Product model"""
    class Meta:
        model = Product
    
    title = factory.Sequence(lambda n: f'Book {n}')
    category = Product.Category.OTHER
    description = 'Test description'
    price = factory.Faker('random_int', min=50000, max=500000)
    active = True
    stock = factory.Faker('random_int', min=1, max=100)
    discount_percent = 0
    special_price = 0
    author = factory.Faker('name')
    publisher = factory.Faker('company')
    isbn = factory.Faker('isbn13')
    number_of_pages = factory.Faker('random_int', min=50, max=500)
    weight = factory.Faker('random_int', min=100, max=2000)
    datetime_created = factory.LazyFunction(timezone.now)

class PackageFactory(factory.django.DjangoModelFactory):
    """Factory for Package model"""
    class Meta:
        model = Package
    
    title = factory.Sequence(lambda n: f'Package {n}')
    slug = factory.Sequence(lambda n: f'package-{n}')
    description = 'Test package'
    active = True
    stock = factory.Faker('random_int', min=1, max=50)
    original_price = 0
    price = 0
    manual_price = 0
    discount_percent = 0
    
    @factory.post_generation
    def products(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            # محصولات را اضافه کن
            for product in extracted:
                self.products.add(product)
            
            # حالا قیمت‌ها را به‌روزرسانی کن
            self._update_prices()
class CommentFactory(factory.django.DjangoModelFactory):
    """Factory for Comment model"""
    class Meta:
        model = Comment
    
    product = factory.SubFactory(ProductFactory)
    author = factory.SubFactory('accounts.factories.UserFactory')
    body = factory.Faker('paragraph', nb_sentences=3)
    stars = factory.Faker('random_int', min=1, max=5)
    active = False


class DiscountCodeFactory(factory.django.DjangoModelFactory):
    """Factory for DiscountCode model"""
    class Meta:
        model = DiscountCode
    
    code = factory.Sequence(lambda n: f'DISCOUNT{n}')
    percent = factory.Faker('random_int', min=5, max=50)
    amount = 0
    max_uses = factory.Faker('random_int', min=1, max=10)
    used_count = 0
    active = True


class FAQFactory(factory.django.DjangoModelFactory):
    """Factory for FAQ model"""
    class Meta:
        model = FAQ
    
    question = factory.Sequence(lambda n: f'Question {n}?')
    answer = 'Test answer'
    order = factory.Sequence(lambda n: n)
    is_active = True


class ProductBlogFactory(factory.django.DjangoModelFactory):
    """Factory for ProductBlog model"""
    class Meta:
        model = ProductBlog
    
    product = factory.SubFactory(ProductFactory)
    title = factory.Sequence(lambda n: f'Blog {n}')
    content = 'Test content'
    blog_type = ProductBlog.BlogType.ARTICLE
    is_active = True


class InstallmentPlanFactory(factory.django.DjangoModelFactory):
    """Factory for InstallmentPlan model"""
    class Meta:
        model = InstallmentPlan
    
    product = factory.SubFactory(ProductFactory)
    month_count = 3
    prepayment_percent = 30
    is_active = True