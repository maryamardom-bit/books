from django.urls import path
from . import views

app_name = 'product'

urlpatterns = [
    path('', views.ProductListView.as_view(), name='product_list'),
    path('<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('comment/<int:product_id>/', views.CommentCreateView.as_view(), name='comment_create'),
    path('search/', views.ProductSearchView.as_view(), name='product_search'),
    path('categories/', views.category_list, name='product_category'),
    path('categories/<str:category>/', views.product_list_by_category, name='product_list_by_category'),
    path('packages/', views.PackageListView.as_view(), name='package_list'),
    path('packages/<slug:slug>/', views.PackageDetailView.as_view(), name='package_detail'),
    path('packages/<slug:slug>/comment/', views.package_comment, name='package_comment'),
    path('author/<str:author_name>/', views.author_books_view, name='author_books'),
    path('best-sellers/', views.BestSellersView.as_view(), name='best_sellers'),
]