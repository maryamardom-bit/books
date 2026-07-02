from django.urls import path

from . import views

urlpatterns = [
    path('' , views.HomePageView.as_view() , name = 'home'),
    path('orderus/' , views.OrderUsPageView.as_view() , name = 'orderus'),
    path('aboutus/' , views.AboutUsPageView.as_view() , name = 'aboutus'),
    path('contactus/' , views.ContactUsPageView.as_view() , name = 'contactus'),
    path('workingus/' , views.WorkingUsPageView.as_view() , name = 'workingus'),

]
