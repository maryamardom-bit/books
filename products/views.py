from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.views import generic
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.db.models import Q

from .models import Product,Comment
from .forms import CommentForm
from cart.forms import AddToCartProductForm

class ProductListView(generic.ListView):
    model = Product
    queryset = Product.objects.filter(active = True)
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
             obj = form.save(commit= False)
             obj.author = self.request.user
             
             product_id = int(self.kwargs['product_id'])
             product = get_object_or_404(Product , id = product_id)

             obj.product = product
             messages.success(self.request,_('your comment has been succsessfully registered '))
             return super().form_valid(form)
        

# :white_check_mark: ویو جستجوی جدید
class ProductSearchView(generic.ListView):
    model = Product
    template_name = 'Products/product_search_results.html'
    context_object_name = 'results'
    paginate_by = 20  # صفحه‌بندی ۲۰ کتاب در هر صفحه

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        if query:
            return Product.objects.filter(
                Q(title__icontains=query) |
                Q(author__icontains=query) |      # اگر فیلد author دارید
                Q(publisher__icontains=query) |   # اگر فیلد publisher دارید
                Q(description__icontains=query) |
                Q(categorynameicontains=query)  # جستجو در نام دسته‌بندی
            ).filter(active=True).distinct()
        return Product.objects.none()  # اگر عبارت خالی بود، هیچ نتیجه‌ای برنگردان

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context


