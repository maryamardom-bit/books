from django.shortcuts import render

from django.views.generic import TemplateView

class HomePageView(TemplateView):
    template_name = 'home.html'

class AboutusView(TemplateView):
    template_name ='pages/aboutus.html'
