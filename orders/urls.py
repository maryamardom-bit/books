from django.urls import path
from . import views

app_name = 'order'

urlpatterns = [
    path('create/', views.order_create_view, name='order_create'),
    path('return/<int:order_id>/', views.request_return_view, name='request_return'),
    path('returns/', views.my_returns_view, name='my_returns'),
]