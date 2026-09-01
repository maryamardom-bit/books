import factory
from django.utils import timezone
from .models import Order, OrderItem, ReturnRequest


class OrderFactory(factory.django.DjangoModelFactory):
    """Factory for Order model"""
    class Meta:
        model = Order
    
    user = factory.SubFactory('accounts.factories.UserFactory')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    phone_number = factory.LazyFunction(lambda: '09123456789')  # شماره ثابت با طول مناسب
    address = factory.Faker('address')
    total_price = factory.Faker('random_int', min=100000, max=1000000)
    total_weight = factory.Faker('random_int', min=100, max=5000)
    is_paid = True
    datetime_created = factory.LazyFunction(timezone.now)


class OrderItemFactory(factory.django.DjangoModelFactory):
    """Factory for OrderItem model"""
    class Meta:
        model = OrderItem
    
    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory('products.factories.ProductFactory')
    package = None  # به صورت پیش‌فرض None
    quantity = factory.Faker('random_int', min=1, max=5)
    price = factory.Faker('random_int', min=50000, max=500000)


class ReturnRequestFactory(factory.django.DjangoModelFactory):
    """Factory for ReturnRequest model"""
    class Meta:
        model = ReturnRequest
    
    order = factory.SubFactory(OrderFactory)
    user = factory.SubFactory('accounts.factories.UserFactory')
    reason = 'Test return reason'
    status = ReturnRequest.ReturnStatus.PENDING