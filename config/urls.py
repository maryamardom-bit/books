"""config URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.health import health_view


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_view, name='health'),
    path('', include('pages.urls')),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('cart/', include('cart.urls')),
    path('order/', include('orders.urls')),
    path('payment/', include('payment.urls')),
    path('rosetta/', include('rosetta.urls')),
    path('api/auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api/v1/', include('api.urls')),
    # Deprecated unversioned prefix, kept so existing clients keep working.
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if getattr(settings, 'ENABLE_DEBUG_TOOLBAR', False):
    from debug_toolbar.toolbar import debug_toolbar_urls
    urlpatterns += debug_toolbar_urls()
