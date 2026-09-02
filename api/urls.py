from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework import permissions
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from . import views

schema_view = get_schema_view(
    openapi.Info(
        title="Kasra Publishing API",
        default_version='v1',
        description="API for Kasra Publishing bookstore",
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="info@kasra-pub.ir"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

router = DefaultRouter()
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'packages', views.PackageViewSet, basename='package')
router.register(r'comments', views.CommentViewSet, basename='comment')
router.register(r'blogs', views.ProductBlogViewSet, basename='blog')
router.register(r'faqs', views.FAQViewSet, basename='faq')
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'returns', views.ReturnRequestViewSet, basename='return')

urlpatterns = [
    path('', include(router.urls)),
    path('profile/', views.UserProfileView.as_view(), name='api_profile'),
    path('cart/', views.CartAPIView.as_view(), name='api_cart'),
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
    
    # JWT Endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # Swagger URLs
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]