# Smart_Invent/core/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Count # <--- Ensure both are imported here
from django.utils import timezone # <--- Ensure this is imported here

from .models import Product, Category, Sale, SaleItem
from .forms import ProductForm, CustomUserCreationForm, SaleForm, SaleItemFormSet


# Home page view (publicly accessible)
def index(request):
    return render(request, 'index.html')


# Dashboard View (requires login)
@login_required
def dashboard(request):
    # Current month's data
    current_month = timezone.now().month
    current_year = timezone.now().year

    # Aggregate sales for the current month
    monthly_sales_data = Sale.objects.filter(
        sale_date__year=current_year,
        sale_date__month=current_month
    ).aggregate(
        total_sales_count=Count('id'),
        total_sales_amount=Sum('total_amount')
    )

    total_monthly_sales_count = monthly_sales_data['total_sales_count'] or 0
    total_monthly_sales_amount = monthly_sales_data['total_sales_amount'] or 0.00

    # Overall totals
    total_products = Product.objects.count()
    total_sales_overall = Sale.objects.count() # Total number of sales recorded
    total_sales_value_overall = Sale.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00

    # Low stock products (e.g., quantity <= 10)
    low_stock_products = Product.objects.filter(stock_quantity__lte=10).order_by('stock_quantity')
    low_stock_count = low_stock_products.count()

    # Recently added products
    # CORRECTED FIELD NAME: Changed 'date_added' to 'created_at'
    recent_products = Product.objects.all().order_by('-created_at')[:5]

    # Recent sales
    recent_sales = Sale.objects.all().order_by('-sale_date')[:5] # Get last 5

    context = {
        'total_products': total_products,
        'total_sales_overall': total_sales_overall,
        'total_sales_value_overall': total_sales_value_overall,
        'low_stock_products': low_stock_products,
        'low_stock_count': low_stock_count,
        'recent_products': recent_products,
        'recent_sales': recent_sales,
        'total_monthly_sales_count': total_monthly_sales_count,
        'total_monthly_sales_amount': total_monthly_sales_amount,
        'title': 'Dashboard'
    }
    return render(request, 'dashboard.html', context)


# Product List view (requires login)
@login_required
def product_list(request):
    products = Product.objects.all()
    context = {
        'products': products,
        'title': 'Product List'
    }
    return render(request, 'products/product_list.html', context)


# Add Product view (requires login)
@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm()

    context = {
        'form': form,
        'title': 'Add New Product'
    }
    return render(request, 'products/product_form.html', context)


# Edit Product view (requires login)
@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)  # Get product or return 404

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)

    context = {
        'form': form,
        'product': product,
        'title': 'Edit Product'
    }
    return render(request, 'products/product_form.html', context)


# Delete Product view (requires login)
@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)  # Get product or return 404

    if request.method == 'POST':
        product.delete()
        return redirect('product_list')

    context = {
        'product': product,
        'title': 'Confirm Delete Product'
    }
    return render(request, 'products/product_confirm_delete.html', context)


# User Registration view (publicly accessible)
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Log the user in immediately after registration
            return redirect('index')  # Redirect to home page or dashboard
    else:
        form = CustomUserCreationForm()

    context = {
        'form': form,
        'title': 'Register'
    }
    return render(request, 'registration/register.html', context)


# Record Sale view (requires login)
@login_required
def record_sale(request):
    if request.method == 'POST':
        form = SaleForm(request.POST)
        formset = SaleItemFormSet(request.POST, request.FILES, prefix='sale_items')

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():  # Ensures all database operations succeed or fail together
                    sale = form.save(commit=False)
                    sale.total_amount = 0  # Initialize total_amount
                    sale.save()

                    for item_form in formset:
                        # Only process forms that have data and are not marked for deletion (if they were existing)
                        if item_form.has_changed() and not item_form.instance.pk:
                            sale_item = item_form.save(commit=False)
                            product = sale_item.product
                            quantity = sale_item.quantity

                            if product.stock_quantity < quantity:
                                item_form.add_error('quantity',
                                                    f"Not enough stock for {product.name}. Available: {product.stock_quantity}")
                                raise ValueError(f"Insufficient stock for {product.name}")

                            product.stock_quantity -= quantity
                            product.save()

                            sale_item.sale = sale
                            sale_item.price_at_sale = product.price  # Record the price at the time of sale
                            sale_item.save()

                            sale.total_amount += (sale_item.price_at_sale * quantity)

                    sale.save()  # Save the sale again to update the total_amount

                return redirect('product_list')  # Or 'sale_list' once it's fully ready

            except ValueError as e:
                # Stock validation error, re-render form with specific error message
                pass
            except Exception as e:
                # Catch any other unexpected errors during transaction
                form.add_error(None, f"An unexpected error occurred: {e}")

    else:  # GET request
        form = SaleForm()
        formset = SaleItemFormSet(prefix='sale_items')  # Initialize with prefix for consistency

    context = {
        'form': form,
        'formset': formset,
        'title': 'Record New Sale'
    }
    return render(request, 'sales/record_sale.html', context)


# Sale List view (requires login)
@login_required
def sale_list(request):
    sales = Sale.objects.all().order_by('-sale_date')  # Order by most recent first
    context = {
        'sales': sales,
        'title': 'Sales History'
    }
    return render(request, 'sales/sale_list.html', context)


# Sale Detail view (requires login)
@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale, pk=pk)  # Get specific sale or return 404
    context = {
        'sale': sale,
        'title': f'Sale Details (ID: {sale.id})'
    }
    return render(request, 'sales/sale_detail.html', context)