from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.views import generic
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db.models import Q, Count, Avg, Value, IntegerField, Sum, F
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.views.decorators.cache import cache_page

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
        queryset = Product.objects.with_ratings().filter(active=True)
        
        discount_filter = self.request.GET.get('discount', '')
        if discount_filter == 'true':
            queryset = Product.objects.with_ratings().filter(
                active=True
            ).filter(
                Q(special_price__gt=0) | Q(discount_percent__gt=0)
            )
        
        sort = self.request.GET.get('sort', '-datetime_created')
        sort_options = {
            'price': 'price',
            '-price': '-price',
            'title': 'title',
            'author': 'author',
            'newest': '-datetime_created',
            'oldest': 'datetime_created',
            'rating': '-avg_rating',
        }
        sort_field = sort_options.get(sort, '-datetime_created')
        
        return queryset.order_by(sort_field)

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

    def get_queryset(self):
        return Product.objects.filter(active=True).prefetch_related(
            'comments__author',
            'blogs',
            'installment_plans',
            'packages',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_form'] = CommentForm()
        
        product = context['product']
        context['is_on_sale'] = product.is_on_sale()
        context['discounted_price'] = product.get_discounted_price()
        context['savings'] = product.get_savings()
        context['discount_percentage'] = product.get_discount_percent_display()
        
        cache_key = f'related_products_{product.pk}'
        related_products = cache.get(cache_key)
        
        if related_products is None:
            related_products = Product.objects.filter(
                active=True
            ).filter(
                Q(category=product.category) | Q(author=product.author)
            ).exclude(id=product.id).distinct()[:4]
            cache.set(cache_key, related_products, 600)
        
        context['related_products'] = related_products
        
        if product.author:
            cache_key_author = f'author_books_{product.author}_{product.pk}'
            author_books = cache.get(cache_key_author)
            
            if author_books is None:
                author_books = Product.objects.filter(
                    active=True,
                    author=product.author
                ).exclude(id=product.id)[:6]
                cache.set(cache_key_author, author_books, 600)
            
            context['author_books'] = author_books
        
        context['blogs'] = product.blogs.filter(is_active=True)
        context['active_comments'] = product.comments.filter(active=True).select_related('author')
        
        return context


class CommentCreateView(generic.View):
    """Submit new comment"""
    
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id, active=True)
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
            return Product.objects.with_ratings().filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(author__icontains=query) |
                Q(publisher__icontains=query) |
                Q(isbn__icontains=query),
                active=True
            ).order_by('-datetime_created').distinct()
        
        return Product.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
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
    
    def get_queryset(self):
        return Package.objects.filter(active=True).prefetch_related('products')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['add_to_cart_form'] = AddToCartProductForm()
        context['is_in_stock'] = context['package'].is_in_stock()
        context['total_weight'] = context['package'].get_total_weight()
        return context


@cache_page(60 * 5)
def category_list(request):
    """Display all categories with counts"""
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
    
    category_counts = dict(
        Product.objects.filter(active=True).values_list('category').annotate(
            count=Count('id')
        )
    )
    
    for category_code, category_name in Product.Category.choices:
        if category_code in EXCLUDED_CATEGORIES:
            continue
        
        categories.append({
            'code': category_code,
            'name': category_name,
            'icon': icons.get(category_code, '📚'),
            'count': category_counts.get(category_code, 0),
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
    
    products_list = Product.objects.with_ratings().filter(category=category, active=True)
    
    sort = request.GET.get('sort', '-datetime_created')
    sort_options = {
        'price': 'price',
        '-price': '-price',
        'title': 'title',
        'rating': '-avg_rating',
    }
    products_list = products_list.order_by(sort_options.get(sort, '-datetime_created'))
    
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
        package = get_object_or_404(Package, slug=slug, active=True)
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
    books = Product.objects.with_ratings().filter(
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
        return Product.objects.with_sales_count().filter(
            active=True,
            order_items__order__is_paid=True
        ).order_by('-total_sold_calc').distinct()[:20]