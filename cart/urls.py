from django.urls import path
from .views import (
    cart_detail_view,
    add_to_cart_view,
    add_package_to_cart_view,
    remove_from_cart,
    remove_package_from_cart,
    clear_cart,
    apply_discount_code_view,
    remove_discount_code_view,
)

app_name = 'cart'

urlpatterns = [
    path('', cart_detail_view, name='cart_detail'),
    path('add/<int:product_id>/', add_to_cart_view, name='cart_add'),
    path('add-package/<int:package_id>/', add_package_to_cart_view, name='cart_add_package'),
    path('remove/<int:product_id>/', remove_from_cart, name='cart_remove'),
    path('remove-package/<int:package_id>/', remove_package_from_cart, name='cart_remove_package'),
    path('clear/', clear_cart, name='cart_clear'),
    path('apply-discount/', apply_discount_code_view, name='apply_discount'),
    path('remove-discount/', remove_discount_code_view, name='remove_discount'),
]