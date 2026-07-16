from django.contrib import admin
from jalali_date.admin import ModelAdminJalaliMixin
from django.utils.translation import gettext_lazy as _

from .models import Product,Comment

class CommentsInLine(admin.TabularInline):
    model = Comment
    fields = ['author','body' , 'stars' , 'active',]
    extra = 0
    readonly_fields = ['datetime_created']


@admin.register(Product)
class ProductAdmin(ModelAdminJalaliMixin,admin.ModelAdmin):
    list_display = ['title','category','author','publisher','price','active',]
    list_filter = ['category', 'active','book_size','cover_type','publication_year',]
    search_fields = ['title', 'description','author','publisher','isbn']
    list_editable = ['price', 'active']
    readonly_fields = ['datetime_created', 'datetime_modified']
    list_per_page = 20
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'title', 
                'category', 
                'description', 
                'price', 
                'image'
            )
        }),
        (_('Book Details'), {
            'fields': (
                'author', 
                'publisher',
                'edition', 
                'isbn', 
                'publication_year',
                'Printing_time', 
                'pages', 
                'book_size', 
                'cover_type'
            ),
            'classes': ('wide', 'extrapretty'),
        }),
        (_('Status & Dates'), {
            'fields': (
                'active', 
                'datetime_created', 
                'datetime_modified'
            ),
            'classes': ('collapse',),
        }),
    )
   

    inlines =[
        CommentsInLine ,
    ]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['product' , 'author','body' , 'stars' , 'active',]
    list_filter = [
        'active', 
        'stars', 
        'datetime_created'
    ]
    search_fields = [
        'author__username', 
        'product__title', 
        'body'
    ]
    list_editable = ['active']
    list_per_page = 20
    ordering = ['-datetime_created']



    
    
    
    
 