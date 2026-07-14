from django.contrib import admin
from jalali_date.admin import ModelAdminJalaliMixin

from .models import Product,Comment

class CommentsInLine(admin.TabularInline):
    model = Comment
    fields = ['author','body' , 'stars' , 'active',]
    extra = 0

@admin.register(Product)
class ProductAdmin(ModelAdminJalaliMixin,admin.ModelAdmin):
    list_display = ['title' , 'category', 'price' , 'active',]
    list_filter = ['category', 'active']
    search_fields = ['title', 'description']

    inlines =[
        CommentsInLine ,
    ]

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['product' , 'author','body' , 'stars' , 'active',]



 