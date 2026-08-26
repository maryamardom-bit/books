from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.views import generic
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db.models import Q, Count, Avg, Value, IntegerField, Sum
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Product, Comment, Package, ProductBlog, InstallmentPlan
from .forms import CommentForm
from cart.forms import AddToCartProductForm


class ProductListView(generic.ListView):
    """List products with filters and sorting"""
    model = Product
    template_name = 'Products/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        queryset = Product.objects.filter(active=True)
        
        # Discount filter
        discount_filter = self.request.GET.get('discount', '')
        if discount_filter == 'true':
            queryset = Product.objects.get_on_sale_products()
        
        # Sorting
        sort = self.request.GET.get('sort', '-datetime_created')
        
        sort_options = {
            'price': 'price',
            '-price': '-price',
            'title': 'title',
            'author': 'author',
            'newest': '-datetime_created',
            'oldest': 'datetime_created',
        }
        
        sort_field = sort_options.get(sort, '-datetime_created')
        queryset = queryset.order_by(sort_field)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['discount_filter'] = self.request.GET.get('discount', '') == 'true'
        context['sort'] = self.request.GET.get('sort', '-datetime_created')
        
        return context


class ProductDetailView(generic.DetailView):
    """Product detail with related products, blogs, and installments"""
    model = Product
    template_name = 'Products/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_form'] = CommentForm()
        
        product = context['product']
        context['is_on_sale'] = product.is_on_sale()
        context['discounted_price'] = product.get_discounted_price()
        context['savings'] = product.get_savings()
        context['discount_percentage'] = product.get_discount_percent_display()
        
        # Related products
        related_products = Product.objects.filter(
            active=True
        ).filter(
            Q(category=product.category) | Q(author=product.author)
        ).exclude(id=product.id).distinct()[:4]
        context['related_products'] = related_products
        
        # Author books
        if product.author:
            author_books = Product.objects.filter(
                active=True,
                author=product.author
            ).exclude(id=product.id)[:6]
            context['author_books'] = author_books
        
        # Product blogs
        context['blogs'] = product.blogs.filter(is_active=True)
        
        
        return context


class CommentCreateView(generic.View):
    """Submit new comment"""
    
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        body = request.POST.get('body')
        stars = request.POST.get('stars')
        
        if body and stars:
            Comment.objects.create(
                product=product,
                author=request.user,
                body=body,
                stars=int(stars),
                active=False,
            )
            messages.success(request, _('Your comment has been submitted and will be shown after approval.'))
        else:
            messages.error(request, _('Please fill all fields.'))
        
        return redirect('product:product_detail', pk=product_id)


class ProductSearchView(generic.ListView):
    """Search products"""
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
    """List packages"""
    model = Package
    template_name = 'Products/package_list.html'
    context_object_name = 'packages'
    paginate_by = 12
    
    def get_queryset(self):
        return Package.objects.filter(active=True).prefetch_related('products')


class PackageDetailView(generic.DetailView):
    """Package detail"""
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
    """Display all categories"""
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
    """Display books by category"""
    valid_categories = dict(Product.Category.choices)
    
    if category not in valid_categories:
        return render(request, 'Products/product_list_by_category.html', {
            'products': Product.objects.none(),
            'category': None,
            'error': _('Invalid category'),
        })
    
    products_list = Product.objects.filter(category=category, active=True)
    
    sort = request.GET.get('sort', '-datetime_created')
    if sort == 'price':
        products_list = products_list.order_by('price')
    elif sort == '-price':
        products_list = products_list.order_by('-price')
    elif sort == 'title':
        products_list = products_list.order_by('title')
    else:
        products_list = products_list.order_by('-datetime_created')
    
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
    """Submit comment for package"""
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
                    active=False,
                )
                messages.success(request, _('Your comment has been submitted and will be shown after approval.'))
            else:
                messages.error(request, _('This package has no products.'))
        else:
            messages.error(request, _('Please fill all fields.'))
        
        return redirect('product:package_detail', slug=slug)
    
    return redirect('product:package_detail', slug=slug)


def author_books_view(request, author_name):
    """Display books by specific author"""
    books = Product.objects.filter(
        author=author_name,
        active=True
    ).order_by('-datetime_created')
    
    paginator = Paginator(books, 12)
    page = request.GET.get('page', 1)
    
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
    
    context = {
        'author': author_name,
        'products': products,
        'total_books': books.count(),
        'is_paginated': products.has_other_pages(),
        'page_obj': products,
    }
    
    return render(request, 'Products/author_books.html', context)


class BestSellersView(generic.ListView):
    """Best selling products"""
    model = Product
    template_name = 'Products/best_sellers.html'
    context_object_name = 'products'
    paginate_by = 12
    
    def get_queryset(self):
        return Product.objects.filter(
            active=True,
            order_items__order__is_paid=True
        ).annotate(
            total_sold=Sum('order_items__quantity')
        ).order_by('-total_sold')[:20]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context