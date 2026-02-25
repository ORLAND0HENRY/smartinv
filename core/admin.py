# sales_inventory_system/core/admin.py
from django.contrib import admin
from .models import Category, Product, Sale, SaleItem

# Register your models here.
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Sale)
admin.site.register(SaleItem)

