from rest_framework import serializers
from django.contrib.auth import get_user_model
from products.models import Product, Package, Comment, ProductBlog, FAQ
from orders.models import Order, OrderItem, ReturnRequest
import jdatetime
from django.utils import timezone

User = get_user_model()


def to_jalali(dt):
    """Convert datetime to Jalali string"""
    if not dt:
        return None
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    j_date = jdatetime.datetime.fromgregorian(datetime=dt)
    return j_date.strftime('%Y/%m/%d - %H:%M')


class ProductSerializer(serializers.ModelSerializer):
    discounted_price = serializers.SerializerMethodField()
    savings = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    is_on_sale = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    datetime_created = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'category', 'category_display', 'description',
            'price', 'discounted_price', 'savings', 'image', 'author',
            'publisher', 'isbn', 'year_of_publication', 'number_of_pages',
            'weight', 'stock', 'available_stock', 'is_on_sale',
            'avg_rating', 'datetime_created',
        ]
    
    def get_discounted_price(self, obj):
        return obj.get_discounted_price()
    
    def get_savings(self, obj):
        return obj.get_savings()
    
    def get_avg_rating(self, obj):
        return obj.avg_rating
    
    def get_is_on_sale(self, obj):
        return obj.is_on_sale()
    
    def get_datetime_created(self, obj):
        return to_jalali(obj.datetime_created)


class PackageSerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True, read_only=True)
    products_count = serializers.SerializerMethodField()
    total_weight = serializers.SerializerMethodField()
    savings = serializers.SerializerMethodField()
    datetime_created = serializers.SerializerMethodField()
    
    class Meta:
        model = Package
        fields = [
            'id', 'title', 'slug', 'description', 'image',
            'products', 'products_count', 'original_price', 'price',
            'discount_percent', 'savings', 'stock', 'total_weight',
            'active', 'datetime_created',
        ]
    
    def get_products_count(self, obj):
        return obj.get_products_count()
    
    def get_total_weight(self, obj):
        return obj.get_total_weight()
    
    def get_savings(self, obj):
        return obj.calculate_savings()
    
    def get_datetime_created(self, obj):
        return to_jalali(obj.datetime_created)


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)
    datetime_created = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'product', 'author_name', 'body', 'stars',
            'datetime_created', 'active',
        ]
    
    def get_datetime_created(self, obj):
        return to_jalali(obj.datetime_created)


class ProductBlogSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source='product.title', read_only=True)
    datetime_created = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductBlog
        fields = [
            'id', 'product', 'product_title', 'title', 'content',
            'blog_type', 'video', 'author_name', 'datetime_created',
        ]
    
    def get_datetime_created(self, obj):
        return to_jalali(obj.datetime_created)


class FAQSerializer(serializers.ModelSerializer):
    datetime_created = serializers.SerializerMethodField()
    
    class Meta:
        model = FAQ
        fields = [
            'id', 'question', 'answer', 'order', 'is_active',
            'datetime_created',
        ]
    
    def get_datetime_created(self, obj):
        return to_jalali(obj.datetime_created)


class OrderItemSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'package', 'quantity', 'price', 'title']
    
    def get_title(self, obj):
        return obj.get_title()


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    datetime_created = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'user', 'is_paid', 'first_name', 'last_name',
            'phone_number', 'address', 'total_weight', 'total_price',
            'payment_method', 'items', 'datetime_created',
        ]
    
    def get_datetime_created(self, obj):
        return to_jalali(obj.datetime_created)


class ReturnRequestSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    datetime_created = serializers.SerializerMethodField()
    
    class Meta:
        model = ReturnRequest
        fields = [
            'id', 'order', 'user', 'reason', 'status', 'status_display',
            'admin_note', 'datetime_created',
        ]
    
    def get_datetime_created(self, obj):
        return to_jalali(obj.datetime_created)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'address', 'birth_date', 'wallet_balance',
        ]
        read_only_fields = ['id', 'username', 'email', 'wallet_balance']