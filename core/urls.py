from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/edit/<int:pk>/', views.edit_product, name='edit_product'),
    path('products/delete/<int:pk>/', views.delete_product, name='delete_product'),
    path('products/export/', views.export_products_csv, name='export_products_csv'),
    path('register/', views.register, name='register'),
    path('sales/record/', views.record_sale, name='record_sale'),
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/export/', views.export_sales_csv, name='export_sales_csv'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('analytics/', views.sales_analytics, name='sales_analytics'),
    path('sales/report/', views.sales_report, name='sales_report'),
]
