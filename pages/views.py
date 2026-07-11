from django.shortcuts import render
from django.views.generic import TemplateView
from .models import ContactInfo
from .models import CooperationInfo

class HomePageView(TemplateView):
    template_name = 'home.html'

class OrderUsPageView(TemplateView):
    template_name ='pages/orderus.html'

class AboutUsPageView(TemplateView):
    template_name ='pages/aboutus.html'
    
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

