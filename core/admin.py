# Smart_Invent/core/admin.py
from django.contrib import admin
from .models import Category, Product, Sale, SaleItem # Import your new models

# Register your models here.
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Sale)
admin.site.register(SaleItem)

# Optional: Customize how models appear in the admin
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ('name', 'category', 'price', 'stock_quantity', 'sku', 'get_stock_status', 'created_at')
#     list_filter = ('category', 'created_at')
#     search_fields = ('name', 'sku')
#     readonly_fields = ('created_at', 'updated_at')
#
# admin.site.register(Product, ProductAdmin)

# class SaleAdmin(admin.ModelAdmin):
#     list_display = ('id', 'user', 'sale_date', 'total_amount')
#     list_filter = ('sale_date', 'user')
#     search_fields = ('user__username',) # Search by username of the related user
#     date_hierarchy = 'sale_date' # Adds a date drill-down navigation
#
# admin.site.register(Sale, SaleAdmin)