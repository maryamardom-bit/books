from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.views import generic
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db.models import Q, Count, Avg, Value, IntegerField
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Product, Comment, Package
from .forms import CommentForm
from cart.forms import AddToCartProductForm


class ProductListView(generic.ListView):
    model = Product
    template_name = 'Products/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        queryset = Product.objects.filter(active=True)
        
        # فیلتر تخفیف
        discount_filter = self.request.GET.get('discount', '')
        if discount_filter == 'true':
            queryset = Product.objects.get_on_sale_products()
        
        # مرتب‌سازی
        sort = self.request.GET.get('sort', '-datetime_created')
        
        if sort == 'price':
            queryset = queryset.order_by('price')
        elif sort == '-price':
            queryset = queryset.order_by('-price')
        elif sort == 'title':
            queryset = queryset.order_by('title')
        elif sort == 'author':
            queryset = queryset.order_by('author')
        elif sort == 'newest':
            queryset = queryset.order_by('-datetime_created')
        elif sort == 'oldest':
            queryset = queryset.order_by('datetime_created')
        else:
            queryset = queryset.order_by('-datetime_created')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['discount_filter'] = self.request.GET.get('discount', '') == 'true'
        context['sort'] = self.request.GET.get('sort', '-datetime_created')
        
        # اضافه کردن اطلاعات تخفیف برای هر محصول
        if context.get('products'):
            for product in context['products']:
                product.final_price = product.get_discounted_price()
                product.savings_amount = product.get_savings()
                product.discount_percentage = product.get_discount_percent_display()
        
        return context


class ProductDetailView(generic.DetailView):
    model = Product
    template_name = 'Products/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_form'] = CommentForm()
        
        # اطلاعات تخفیف
        product = context['product']
        context['is_on_sale'] = product.is_on_sale()
        context['discounted_price'] = product.get_discounted_price()
        context['savings'] = product.get_savings()
        context['discount_percentage'] = product.get_discount_percent_display()
        
        # محصولات مرتبط (همین دسته یا همین نویسنده)
        related_products = Product.objects.filter(
            active=True
        ).filter(
            Q(category=product.category) | Q(author=product.author)
        ).exclude(id=product.id).distinct()[:4]
        
        context['related_products'] = related_products
        
        # کتاب‌های دیگر همین نویسنده
        if product.author:
            author_books = Product.objects.filter(
                active=True,
                author=product.author
            ).exclude(id=product.id)[:6]
            context['author_books'] = author_books
        
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
        
        messages.success(self.request, _('Your comment has been successfully registered.'))
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
                Q(author__icontains=query) |
                Q(publisher__icontains=query) |
                Q(isbn__icontains=query) |
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


class PackageListView(generic.ListView):
    """نمایش لیست پکیج‌ها"""
    model = Package
    template_name = 'Products/package_list.html'
    context_object_name = 'packages'
    paginate_by = 12
    
    def get_queryset(self):
        return Package.objects.filter(active=True).prefetch_related('products')


class PackageDetailView(generic.DetailView):
    """نمایش جزییات یک پکیج"""
    model = Package
    template_name = 'Products/package_detail.html'
    context_object_name = 'package'
    slug_url_kwarg = 'slug'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['add_to_cart_form'] = AddToCartProductForm()
        context['is_in_stock'] = context['package'].is_in_stock()
        context['total_weight'] = context['package'].get_total_weight()
        return context


def category_list(request):
    """نمایش همه دسته‌بندی‌ها"""
    categories = []
    
    EXCLUDED_CATEGORIES = ['PACKAGES']
    
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
    }
    
    for category_code, category_name in Product.Category.choices:
        if category_code in EXCLUDED_CATEGORIES:
            continue
            
        product_count = Product.objects.filter(category=category_code, active=True).count()
        
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
    """نمایش کتاب‌های یک دسته خاص"""
    valid_categories = dict(Product.Category.choices)
    
    if category not in valid_categories:
        return render(request, 'Products/product_list_by_category.html', {
            'products': Product.objects.none(),
            'category': None,
            'error': 'دسته‌بندی نامعتبر است',
        })
    
    products_list = Product.objects.filter(category=category, active=True)
    
    # مرتب‌سازی
    sort = request.GET.get('sort', '-datetime_created')
    if sort == 'price':
        products_list = products_list.order_by('price')
    elif sort == '-price':
        products_list = products_list.order_by('-price')
    elif sort == 'title':
        products_list = products_list.order_by('title')
    else:
        products_list = products_list.order_by('-datetime_created')
    
    # صفحه‌بندی
    paginator = Paginator(products_list, 12)
    page = request.GET.get('page', 1)
    
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
    
    category_display = valid_categories.get(category, category)
    
    category_icons = {
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
        'sort': sort,
    })


def package_comment(request, slug):
    """ثبت نظر برای پکیج"""
    if request.method == 'POST':
        package = get_object_or_404(Package, slug=slug)
        body = request.POST.get('body')
        stars = request.POST.get('stars')
        
        if body and stars:
            first_product = package.products.first()
            if first_product:
                Comment.objects.create(
                    product=first_product,
                    author=request.user,
                    body=body,
                    stars=int(stars),
                    active=True,
                )
                messages.success(request, 'نظر شما با موفقیت ثبت شد.')
            else:
                messages.error(request, 'این پکیج هیچ کتابی ندارد.')
        else:
            messages.error(request, 'لطفاً همه فیلدها را پر کنید.')
        
        return redirect('product:package_detail', slug=slug)
    
    return redirect('product:package_detail', slug=slug)
