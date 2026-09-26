import json

from django.utils.translation import gettext_lazy as _
from django.utils.html import strip_tags
from django.views import generic
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Product, Comment, Package
from .forms import CommentForm
from .search import build_search_q
from .taxonomy import catalog_subjects, EXCLUDED_CATEGORIES
from cart.forms import AddToCartProductForm


class ProductListView(generic.ListView):
    """List products with filters and sorting"""
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        queryset = Product.objects.with_ratings().filter(active=True)

        discount_filter = self.request.GET.get('discount', '')
        if discount_filter == 'true':
            queryset = queryset.filter(
                Q(special_price__gt=0) | Q(discount_percent__gt=0)
            )

        category = self.request.GET.get('category', '')
        if category in dict(Product.Category.choices) and category not in EXCLUDED_CATEGORIES:
            queryset = queryset.filter(category=category)

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
        context['active_category'] = self.request.GET.get('category', '')
        context['subjects'] = catalog_subjects()
        active = context['active_category']
        context['active_subject'] = next((s for s in context['subjects'] if s['code'] == active), None)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['pagination_extra'] = '&{0}'.format(params.urlencode()) if params else ''
        return context


class ProductDetailView(generic.DetailView):
    """Product detail with related products, blogs, and installments"""
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'

    def get_queryset(self):
        return Product.objects.with_ratings().filter(active=True).prefetch_related(
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
        context['product_packages'] = product.packages.filter(active=True)
        context['json_ld'] = json.dumps(_book_json_ld(product, self.request), ensure_ascii=False)
        return context


def _book_json_ld(product, request):
    image = None
    if product.image:
        image = request.build_absolute_uri(product.image.url)
    data = {
        '@context': 'https://schema.org',
        '@type': 'Book',
        'name': product.title,
        'description': strip_tags(product.description or '')[:400],
        'url': request.build_absolute_uri(product.get_absolute_url()),
        'inLanguage': 'fa',
        'publisher': {
            '@type': 'Organization',
            'name': product.publisher or str(_('Kasra Publishing')),
        },
        'offers': {
            '@type': 'Offer',
            'price': product.get_discounted_price(),
            'priceCurrency': 'IRR',
            'availability': (
                'https://schema.org/InStock'
                if product.available_stock > 0
                else 'https://schema.org/OutOfStock'
            ),
        },
    }
    if product.author:
        data['author'] = {'@type': 'Person', 'name': product.author}
    if product.isbn:
        data['isbn'] = product.isbn
    if product.number_of_pages:
        data['numberOfPages'] = product.number_of_pages
    if image:
        data['image'] = image
    return data


class CommentCreateView(LoginRequiredMixin, generic.View):
    """Submit new comment. Login is required, otherwise anonymous users get a 500 error."""
    def get(self, request, product_id):
        return redirect('product:product_detail', pk=product_id)
    
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
    """Search products (simple across all book fields, or advanced by selected fields)."""
    model = Product
    template_name = 'products/product_search_result.html'
    context_object_name = 'results'
    paginate_by = 20

    def _search_query(self):
        return self.request.GET.get('q', '').strip()

    def _search_mode(self):
        mode = self.request.GET.get('mode', 'simple')
        return mode if mode in ('simple', 'advanced') else 'simple'

    def _selected_fields(self):
        if self._search_mode() != 'advanced':
            return None
        return self.request.GET.getlist('fields')

    def get_queryset(self):
        query = self._search_query()
        q_obj = build_search_q(query, self._selected_fields())
        if q_obj is None:
            return Product.objects.none()
        return Product.objects.with_ratings().filter(
            q_obj,
            active=True,
        ).order_by('-datetime_created').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self._search_query()
        mode = self._search_mode()
        selected = self.request.GET.getlist('fields')
        context['query'] = query
        context['search_mode'] = mode
        context['selected_fields'] = selected
        params = self.request.GET.copy()
        params.pop('page', None)
        context['pagination_extra'] = '&{0}'.format(params.urlencode()) if params else ''
        context['results_count'] = context['paginator'].count if context.get('paginator') else 0
        if not context['results_count']:
            context['suggested_books'] = Product.objects.with_ratings().filter(active=True).order_by('-datetime_created')[:4]
            context['subjects'] = [s for s in catalog_subjects() if s['count']]
        return context


class PackageListView(generic.ListView):
    """List packages"""
    model = Package
    template_name = 'products/package_list.html'
    context_object_name = 'packages'
    paginate_by = 12
    
    def get_queryset(self):
        return Package.objects.filter(active=True).prefetch_related('products')


class PackageDetailView(generic.DetailView):
    """Package detail"""
    model = Package
    template_name = 'products/package_detail.html'
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


def category_list(request):
    """Display architecture subjects with counts."""
    return render(request, 'products/category_list.html', {
        'categories': catalog_subjects(),
    })


def product_list_by_category(request, category):
    """Display books by category"""
    valid_categories = dict(Product.Category.choices)
    
    if category not in valid_categories:
        return render(request, 'products/product_list_by_category.html', {
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

    return render(request, 'products/product_list_by_category.html', {
        'products': products,
        'category': {
            'name': category_display,
            'code': category,
            'slug': category,
            'blurb': next((s['blurb'] for s in catalog_subjects() if s['code'] == category), ''),
            'count': products_list.count(),
        },
        'subjects': catalog_subjects(),
        'paginator': paginator,
        'is_paginated': products.has_other_pages(),
        'page_obj': products,
        'sort': sort,
    })


@login_required
@require_POST
def package_comment(request, slug):
    """Submit comment for package"""
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
    
    return render(request, 'products/author_books.html', context)


def author_list_view(request):
    """Author index derived from catalog — no extra author model."""
    authors = (
        Product.objects.filter(active=True)
        .exclude(author='')
        .values('author')
        .annotate(book_count=Count('id'))
        .order_by('author')
    )
    return render(request, 'products/author_list.html', {
        'authors': authors,
        'total_authors': authors.count(),
    })


class NewReleasesView(generic.ListView):
    """Newest titles from the publisher."""
    model = Product
    template_name = 'products/new_releases.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        return Product.objects.with_ratings().filter(active=True).order_by('-datetime_created')


class BestSellersView(generic.ListView):
    """Best selling products"""
    model = Product
    template_name = 'products/best_sellers.html'
    context_object_name = 'products'
    paginate_by = 12
    
    def get_queryset(self):
        return Product.objects.with_sales_count().filter(
            active=True,
            order_items__order__is_paid=True
        ).order_by('-total_sold').distinct()[:20]