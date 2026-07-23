from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.views import generic
from django.shortcuts import get_object_or_404, render
from django.contrib import messages
from django.db.models import Q, Count, Avg, Value, IntegerField
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Product, Comment
from .forms import CommentForm
from cart.forms import AddToCartProductForm


class ProductListView(generic.ListView):
    model = Product
    queryset = Product.objects.filter(active=True).order_by('-datetime_created')
    paginate_by = 12 
    template_name = 'Products/product_list.html'
    context_object_name = 'products'


class ProductDetailView(generic.DetailView):
    model = Product
    template_name = 'Products/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_form'] = CommentForm()
        return context


class CommentCreateView(generic.CreateView):
    model = Comment
    form_class = CommentForm

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.author = self.request.user
        
        product_id = int(self.kwargs['product_id'])
        product = get_object_or_404(Product, id=product_id)
        obj.product = product
        
        messages.success(self.request, _('your comment has been successfully registered'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('product:product_detail', args=[self.object.product.id])


class ProductSearchView(generic.ListView):
    model = Product
    template_name = 'Products/product_search_result.html'
    context_object_name = 'results'
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        
        if query:
            return Product.objects.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(comments__body__icontains=query)
            ).filter(active=True).annotate(
                comments_count=Count('comments', filter=Q(comments__active=True)),
                avg_stars=Coalesce(Avg('comments__stars'), Value(0), output_field=IntegerField())
            ).order_by('-datetime_created').distinct()
        
        return Product.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['results_count'] = self.get_queryset().count()
        return context

def category_list(request):
    """
    نمایش همه دسته‌بندی‌ها در یک صفحه گرید
    """
    categories = []
    
    # دریافت همه دسته‌بندی‌ها از مدل
    for category_code, category_name in Product.Category.choices:
        # شمارش کتاب‌های هر دسته
        product_count = Product.objects.filter(category=category_code, active=True).count()
        
        # دیکشنری آیکون‌ها
        icons = {
            'BUSINESS': '💼',
            'ARCH_DESIGN': '🏗️',
            'INTERIOR': '🛋️',
            'URBAN': '🏙️',
            'LANDSCAPE': '🌳',
            'DESIGN_GUIDE': '📖',
            'HISTORY': '🏛️',
            'DESIGN_BASICS': '✏️',
            'DIGITAL': '💻',
            'SUSTAIN': '🌿',
            'SAMPLES': '📐',
            'OTHER': '📦',
            'PACKAGES': '📚',
        }
        
        categories.append({
            'code': category_code,
            'name': category_name,
            'icon': icons.get(category_code, '📚'),
            'count': product_count,
        })
    
    return render(request, 'Products/category_list.html', {
        'categories': categories,
    })


def product_list_by_category(request, category):
    """
    نمایش کتاب‌های یک دسته خاص با صفحه‌بندی
    """
    # دریافت همه دسته‌بندی‌های معتبر از مدل
    valid_categories = dict(Product.Category.choices)
    
    # بررسی معتبر بودن دسته
    if category not in valid_categories:
        return render(request, 'Products/product_list_by_category.html', {
            'products': Product.objects.none(),
            'category': None,
            'error': 'دسته‌بندی نامعتبر است'
        })
    
    # فیلتر کردن محصولات بر اساس category
    products_list = Product.objects.filter(category=category, active=True)
    
    # صفحه‌بندی
    paginator = Paginator(products_list, 12)
    page = request.GET.get('page', 1)
    
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
    
    # دریافت نام نمایشی دسته‌بندی
    category_display = valid_categories.get(category, category)
    
    # دیکشنری آیکون‌ها برای هر دسته
    category_icons = {
        'BUSINESS_MANAGEMENT': '💼',
        'ARCHITECTURAL_DESIGN': '🏗️',
        'INTERIOR_DESIGN': '🛋️',
        'URBAN_STUDIES': '🏙️',
        'LANDSCAPE': '🌳',
        'DESIGN_GUIDE': '📖',
        'HISTORY_CRITICISM': '🏛️',
        'DESIGN_FUNDAMENTALS': '✏️',
        'DIGITAL_PARAMETRIC': '💻',
        'SUSTAINABILITY': '🌿',
        'PROJECT_SAMPLES': '📐',
        'OTHER': '📦',
        'PACKAGES': '📚',
    }
    
    return render(request, 'Products/product_list_by_category.html', {
        'products': products,
        'category': {
            'name': category_display,
            'slug': category,
            'icon': category_icons.get(category, '📚'),
            'count': products_list.count(),
        },
        'paginator': paginator,
        'is_paginated': products.has_other_pages(),
        'page_obj': products,
    })