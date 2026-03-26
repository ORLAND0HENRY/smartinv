from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Product, Category, Sale, SaleItem
from .forms import ProductForm, CustomUserCreationForm, SaleForm, SaleItemFormSet


def index(request):
    return render(request, 'index.html', {'title': 'Home'})


@login_required
def dashboard(request):
    today = timezone.now()

    # Optimized aggregation for current month
    stats = Sale.objects.filter(
        sale_date__year=today.year,
        sale_date__month=today.month
    ).aggregate(
        count=Count('id'),
        amount=Sum('total_amount')
    )

    context = {
        'total_products': Product.objects.count(),
        'total_sales_overall': Sale.objects.count(),
        'total_sales_value_overall': Sale.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00,
        'low_stock_products': Product.objects.filter(stock_quantity__lte=10).order_by('stock_quantity'),
        'low_stock_count': Product.objects.filter(stock_quantity__lte=10).count(),
        'recent_products': Product.objects.select_related('category').order_by('-created_at')[:5],
        'recent_sales': Sale.objects.select_related('user').order_by('-sale_date')[:5],
        'total_monthly_sales_count': stats['count'] or 0,
        'total_monthly_sales_amount': stats['amount'] or 0.00,
        'title': 'Dashboard'
    }
    return render(request, 'dashboard.html', context)


@login_required
def product_list(request):
    # select_related reduces SQL hits for category foreign keys
    products = Product.objects.select_related('category').all()
    return render(request, 'products/product_list.html', {
        'products': products,
        'title': 'Product List'
    })


@login_required
def add_product(request):
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('product_list')

    return render(request, 'products/product_form.html', {
        'form': form,
        'title': 'Add New Product'
    })


@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('product_list')

    return render(request, 'products/product_form.html', {
        'form': form,
        'product': product,
        'title': 'Edit Product'
    })


@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        return redirect('product_list')

    return render(request, 'products/product_confirm_delete.html', {
        'product': product,
        'title': 'Confirm Delete'
    })


def register(request):
    form = CustomUserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('index')

    return render(request, 'registration/register.html', {
        'form': form,
        'title': 'Register'
    })


@login_required
def record_sale(request):
    form = SaleForm(request.POST or None)
    formset = SaleItemFormSet(request.POST or None, prefix='sale_items')

    if request.method == 'POST':
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    sale = form.save(commit=False)
                    sale.user = request.user
                    sale.save()

                    items = formset.save(commit=False)
                    for item in items:
                        item.sale = sale
                        item.save()  # Triggers stock deduction in Model.save()

                    sale.update_total()
                return redirect('sale_list')
            except ValidationError as e:
                form.add_error(None, e.message)
            except Exception as e:
                form.add_error(None, f"Transaction failed: {str(e)}")

    return render(request, 'sales/record_sale.html', {
        'form': form,
        'formset': formset,
        'title': 'Record Sale'
    })


@login_required
def sale_list(request):
    sales = Sale.objects.select_related('user').all().order_by('-sale_date')
    return render(request, 'sales/sale_list.html', {
        'sales': sales,
        'title': 'Sales History'
    })


@login_required
def sale_detail(request, pk):

    sale = get_object_or_404(Sale.objects.prefetch_related('items__product'), pk=pk)
    return render(request, 'sales/sale_detail.html', {
        'sale': sale,
        'title': f'Sale Details #{sale.id}'
    })