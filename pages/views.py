from django.db.models import Q, Count
from django.views.generic import TemplateView
from products.models import Product, Package
from products.taxonomy import catalog_subjects
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
        )[:8]
        context['featured_packages'] = Package.objects.filter(active=True)[:3]
        featured = (
            active.exclude(image='').order_by('-datetime_created').first()
            or active.order_by('-datetime_created').first()
        )
        context['featured_book'] = featured
        bestsellers = (
            Product.objects.with_sales_count()
            .filter(active=True, order_items__order__is_paid=True)
            .order_by('-total_sold')
            .distinct()[:8]
        )
        context['bestsellers'] = bestsellers or active.order_by('-avg_rating', '-datetime_created')[:8]
        context['subjects'] = catalog_subjects()
        context['featured_authors'] = list(
            Product.objects.filter(active=True)
            .exclude(author='')
            .values('author')
            .annotate(book_count=Count('id'))
            .order_by('-book_count', 'author')[:10]
        )
        context['catalog_count'] = active.count()
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
    
    