from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from products.models import Product, Package, Comment, ProductBlog, FAQ
from orders.models import Order, ReturnRequest
from cart.cart import Cart
from .serializers import (
    ProductSerializer, PackageSerializer, CommentSerializer,
    ProductBlogSerializer, FAQSerializer, OrderSerializer,
    ReturnRequestSerializer, UserProfileSerializer,
)
from .exceptions import APIError
from .permissions import (
    IsOwnerOrAdmin, IsAdminOrReadOnly, IsProductOwnerOrAdmin,
    IsOrderOwnerOrAdmin,
)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for products"""
    queryset = Product.objects.with_ratings().filter(active=True)
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get list of products",
        manual_parameters=[
            openapi.Parameter('category', openapi.IN_QUERY, description="Filter by category", type=openapi.TYPE_STRING),
            openapi.Parameter('on_sale', openapi.IN_QUERY, description="Filter on sale products", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('search', openapi.IN_QUERY, description="Search products", type=openapi.TYPE_STRING),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        on_sale = self.request.query_params.get('on_sale')
        if on_sale and on_sale.lower() == 'true':
            queryset = queryset.filter(
                Q(special_price__gt=0) | Q(discount_percent__gt=0)
            )
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(author__icontains=search) |
                Q(publisher__icontains=search)
            )
        
        return queryset


class PackageViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for packages"""
    queryset = Package.objects.filter(active=True)
    serializer_class = PackageSerializer
    permission_classes = [AllowAny]


class CommentViewSet(viewsets.ModelViewSet):
    """API endpoint for comments"""
    serializer_class = CommentSerializer
    permission_classes = [IsProductOwnerOrAdmin]
    
    def get_queryset(self):
        product_id = self.request.query_params.get('product')
        queryset = Comment.objects.filter(active=True)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset
    
    def perform_create(self, serializer):
        # نظرات API نیز مانند وب‌سایت نیاز به تایید مدیر دارند
        serializer.save(author=self.request.user, active=False)

    def perform_update(self, serializer):
        # An edited comment goes back to moderation, otherwise approved text could be replaced.
        if self.request.user.is_staff:
            serializer.save()
        else:
            serializer.save(active=False)


class ProductBlogViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for blogs"""
    queryset = ProductBlog.objects.filter(is_active=True)
    serializer_class = ProductBlogSerializer
    permission_classes = [AllowAny]


class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for FAQ"""
    queryset = FAQ.objects.filter(is_active=True).order_by('order', '-datetime_created')
    serializer_class = FAQSerializer
    permission_classes = [AllowAny]


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for orders"""
    serializer_class = OrderSerializer
    permission_classes = [IsOrderOwnerOrAdmin]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)


class ReturnRequestViewSet(viewsets.ModelViewSet):
    """API endpoint for return requests"""
    serializer_class = ReturnRequestSerializer
    permission_classes = [IsOrderOwnerOrAdmin]
    # Customers create and read; status changes happen in the admin workflow.
    http_method_names = ['get', 'post', 'head', 'options']
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return ReturnRequest.objects.all()
        return ReturnRequest.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status='PENDING')


class UserProfileView(APIView):
    """Get or update user profile"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    
    def put(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    patch = put


class CartAPIView(APIView):
    """Cart API for getting, adding, and removing items"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        cart = Cart(request)
        items = []
        
        for item in cart:
            item_id = None
            if item.get('product_obj'):
                item_id = item['product_obj'].id
            elif item.get('package_obj'):
                item_id = item['package_obj'].id
            
            items.append({
                'id': item_id,
                'title': item.get('title'),
                'quantity': item.get('quantity'),
                'price': str(item.get('price')),
                'total_price': str(item.get('total_price')),
                'is_package': item.get('is_package'),
            })
        
        return Response({
            'items': items,
            'total_price': cart.get_total_price(),
            'total_weight': cart.get_total_weight(),
            'total_savings': cart.get_total_savings(),
            'discount_code': cart.discount_code,
            'discounted_total': cart.get_discounted_total(),
        })
    
    MAX_QUANTITY = 100

    @staticmethod
    def _flag(value):
        # JSON sends booleans, form data sends "false"/"0", which are truthy strings.
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(value)

    def _get_item(self, request):
        item_id = request.data.get('item_id')
        if not item_id or not str(item_id).isdigit():
            raise APIError('ITEM_ID_REQUIRED', 'item_id is required')
        is_package = self._flag(request.data.get('is_package', False))
        model = Package if is_package else Product
        item = model.objects.filter(id=item_id).first()
        if item is None:
            raise APIError('ITEM_NOT_FOUND', 'Item not found', status_code=status.HTTP_404_NOT_FOUND)
        return item, is_package

    def post(self, request):
        """Add item to cart"""
        item, is_package = self._get_item(request)
        try:
            quantity = int(request.data.get('quantity', 1))
        except (TypeError, ValueError):
            quantity = 0
        if not 1 <= quantity <= self.MAX_QUANTITY:
            raise APIError('INVALID_QUANTITY', 'Invalid quantity.')

        cart = Cart(request)
        result = cart.add(item, quantity=quantity, is_package=is_package)
        if result == 'out_of_stock':
            raise APIError('BOOK_OUT_OF_STOCK', 'این کتاب موجود نیست.')

        return Response({
            'success': True,
            'limited': result == 'limited',
            'cart_count': len(cart),
            'total_price': cart.get_total_price(),
        })
    
    def delete(self, request):
        """Remove item from cart"""
        item, is_package = self._get_item(request)
        cart = Cart(request)
        cart.remove(item, is_package=is_package)
        
        return Response({
            'success': True,
            'cart_count': len(cart),
            'total_price': cart.get_total_price(),
        })