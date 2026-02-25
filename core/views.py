from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Product, Category, Sale, SaleItem
from .forms import ProductForm, CustomUserCreationForm, SaleForm, SaleItemFormSet

def index(request):
    return render(request, 'index.html')


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



def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = CustomUserCreationForm()

    context = {
        'form': form,
        'title': 'Register'
    }
    return render(request, 'registration/register.html', context)


@login_required
def record_sale(request):
    if request.method == 'POST':
        form = SaleForm(request.POST)
        formset = SaleItemFormSet(request.POST, prefix='sale_items')

        if form.is_valid() and formset.is_valid():
            try:

                with transaction.atomic():
                    sale = form.save(commit=False)
                    sale.user = request.user  # Assign the logged-in user
                    sale.save()

                    # Link the items to the sale and save them
                    # The Model's save() method (updated below) will handle stock & totals
                    instances = formset.save(commit=False)
                    for instance in instances:
                        instance.sale = sale
                        instance.save()

                    sale.update_total()

                return redirect('sale_list')

            except ValidationError as e:
                form.add_error(None, e.message)
            except Exception as e:
                form.add_error(None, f"Critical System Error: {e}")

    else:
        form = SaleForm()
        formset = SaleItemFormSet(prefix='sale_items')

    return render(request, 'sales/record_sale.html', {'form': form, 'formset': formset})

# Sale List view (requires login)
@login_required
def sale_list(request):
    sales = Sale.objects.all().order_by('-sale_date')  # Order by most recent first
    context = {
        'sales': sales,
        'title': 'Sales History'
    }
    return render(request, 'sales/sale_list.html', context)


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale, pk=pk)  # Get specific sale or return 404
    context = {
        'sale': sale,
        'title': f'Sale Details (ID: {sale.id})'
    }
    return render(request, 'sales/sale_detail.html', context)