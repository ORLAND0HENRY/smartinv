import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CustomUserCreationForm, ProductForm, SaleForm, SaleItemFormSet
from .models import Category, Product, Sale

logger = logging.getLogger(__name__)


def index(request):
    return render(request, 'index.html', {'title': 'Home'})


@login_required
def dashboard(request):
    now = timezone.localtime()
    monthly_stats = Sale.objects.filter(
        sale_date__year=now.year,
        sale_date__month=now.month,
    ).aggregate(count=Count('id'), amount=Sum('total_amount'))
    inventory_value = Product.objects.aggregate(
        value=Sum(F('price') * F('stock_quantity')),
    )['value'] or Decimal('0.00')
    low_stock_products = Product.objects.filter(
        stock_quantity__lte=F('low_stock_threshold'),
    ).select_related('category').order_by('stock_quantity', 'name')

    context = {
        'total_products': Product.objects.count(),
        'total_sales_overall': Sale.objects.count(),
        'total_sales_value_overall': Sale.objects.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
        'inventory_value': inventory_value,
        'low_stock_products': low_stock_products[:8],
        'low_stock_count': low_stock_products.count(),
        'recent_products': Product.objects.select_related('category').order_by('-created_at')[:5],
        'recent_sales': Sale.objects.select_related('user').order_by('-sale_date')[:5],
        'total_monthly_sales_count': monthly_stats['count'] or 0,
        'total_monthly_sales_amount': monthly_stats['amount'] or Decimal('0.00'),
        'title': 'Dashboard',
    }
    return render(request, 'dashboard.html', context)


@login_required
def product_list(request):
    products = Product.objects.select_related('category')
    search = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    stock_status = request.GET.get('stock', '').strip()

    if search:
        products = products.filter(name__icontains=search) | products.filter(sku__icontains=search)
    if category_id.isdigit():
        products = products.filter(category_id=category_id)
    if stock_status == 'low':
        products = products.filter(stock_quantity__gt=0, stock_quantity__lte=F('low_stock_threshold'))
    elif stock_status == 'out':
        products = products.filter(stock_quantity=0)
    elif stock_status == 'available':
        products = products.filter(stock_quantity__gt=F('low_stock_threshold'))

    page = Paginator(products.order_by('name'), 25).get_page(request.GET.get('page'))
    return render(request, 'products/product_list.html', {
        'products': page,
        'page_obj': page,
        'categories': Category.objects.order_by('name'),
        'search_query': search,
        'selected_category': category_id,
        'selected_stock': stock_status,
        'title': 'Product List',
    })


@login_required
@permission_required('core.add_product', raise_exception=True)
def add_product(request):
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Product added to inventory.')
        return redirect('product_list')
    return render(request, 'products/product_form.html', {
        'form': form,
        'title': 'Add New Product',
    })


@login_required
@permission_required('core.change_product', raise_exception=True)
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Product updated.')
        return redirect('product_list')
    return render(request, 'products/product_form.html', {
        'form': form,
        'product': product,
        'title': 'Edit Product',
    })


@login_required
@permission_required('core.delete_product', raise_exception=True)
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('product_list')
    return render(request, 'products/product_confirm_delete.html', {
        'product': product,
        'title': 'Confirm Delete',
    })


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = CustomUserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Your account has been created.')
        return redirect('dashboard')
    return render(request, 'registration/register.html', {
        'form': form,
        'title': 'Register',
    })


@login_required
@permission_required('core.add_sale', raise_exception=True)
def record_sale(request):
    form = SaleForm(request.POST or None)
    formset = SaleItemFormSet(request.POST or None, prefix='sale_items')

    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        try:
            with transaction.atomic():
                sale = form.save(commit=False)
                sale.user = request.user
                sale.save()
                for item in formset.save(commit=False):
                    item.sale = sale
                    item.save()
                sale.update_total()
            messages.success(request, f'Sale #{sale.pk} recorded successfully.')
            return redirect('sale_list')
        except ValidationError as error:
            form.add_error(None, error.messages[0])
        except Exception:
            logger.exception('Transaction failed while recording a sale.')
            form.add_error(None, 'The sale could not be processed. Please try again or contact support.')

    return render(request, 'sales/record_sale.html', {
        'form': form,
        'formset': formset,
        'title': 'Record Sale',
    })


@login_required
def sale_list(request):
    sales = Sale.objects.select_related('user').order_by('-sale_date')
    return render(request, 'sales/sale_list.html', {
        'sales': sales,
        'title': 'Sales History',
    })


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related('user').prefetch_related('items__product'),
        pk=pk,
    )
    return render(request, 'sales/sale_detail.html', {
        'sale': sale,
        'title': f'Sale Details #{sale.id}',
    })
