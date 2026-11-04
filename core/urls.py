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
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/edit/<int:pk>/', views.edit_category, name='edit_category'),
    path('categories/delete/<int:pk>/', views.delete_category, name='delete_category'),
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.add_supplier, name='add_supplier'),
    path('suppliers/edit/<int:pk>/', views.edit_supplier, name='edit_supplier'),
    path('suppliers/delete/<int:pk>/', views.delete_supplier, name='delete_supplier'),
    path('purchase-orders/', views.purchase_order_list, name='purchase_order_list'),
    path('purchase-orders/add/', views.add_purchase_order, name='add_purchase_order'),
    path('purchase-orders/<int:pk>/receive/', views.receive_purchase_order, name='receive_purchase_order'),
    path('alerts/low-stock/', views.low_stock_alerts, name='low_stock_alerts'),
    path('alerts/low-stock/send/', views.send_low_stock_alerts, name='send_low_stock_alerts'),
    path('register/', views.register, name='register'),
    path('sales/record/', views.record_sale, name='record_sale'),
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/export/', views.export_sales_csv, name='export_sales_csv'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('analytics/', views.sales_analytics, name='sales_analytics'),
    path('sales/report/', views.sales_report, name='sales_report'),
]
