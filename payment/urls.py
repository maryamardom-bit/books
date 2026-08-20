from django.urls import path
from .views import payment_process, payment_verify

app_name = 'payment'

urlpatterns = [
    path('process/', payment_process, name='payment_process'),
    path('verify/', payment_verify, name='payment_verify'),
]