from django.db.models import Q
from django.views.generic import TemplateView
from products.models import Product
from .models import ContactInfo, CooperationInfo, AboutUs, OrderCondition


class HomePageView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contact'] = ContactInfo.objects.first()
        context['cooperation'] = CooperationInfo.objects.first()
        context['aboutus'] = AboutUs.objects.first()
        active = Product.objects.with_ratings().filter(active=True)
        context['latest_books'] = active.order_by('-datetime_created')[:8]
        context['sale_books'] = active.filter(
            Q(special_price__gt=0) | Q(discount_percent__gt=0)
        )[:4]
        return context


class AboutUsPageView(TemplateView):
    template_name = 'pages/aboutus.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aboutus'] = AboutUs.objects.first()
        context['cooperation'] = CooperationInfo.objects.first()
        return context

class ContactUsPageView(TemplateView):
    template_name ='pages/contactus.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contact'] = ContactInfo.objects.first()
        return context

class WorkingUsPageView(TemplateView):
    template_name = 'pages/workingus.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cooperation'] = CooperationInfo.objects.first()
        return context


class OrderConditionsPageView(TemplateView):
    template_name = 'pages/orderus.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['orderus'] = OrderCondition.objects.first()
        return context
    
    