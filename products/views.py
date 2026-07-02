from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.views import generic
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.db.models import Q, Count, Avg, Value, IntegerField
from django.db.models.functions import Coalesce

from .models import Product, Comment
from .forms import CommentForm
from cart.forms import AddToCartProductForm


class ProductListView(generic.ListView):
    model = Product
    queryset = Product.objects.filter(active=True)
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
        return reverse('product_detail', args=[self.object.product.id])


class ProductSearchView(generic.ListView):
    model = Product
    template_name = 'Products/product_search_result.html'
    context_object_name = 'results'
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        print(f"query:'{query}'")
        
        if query:
            return Product.objects.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(short_discription__icontains=query) |
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