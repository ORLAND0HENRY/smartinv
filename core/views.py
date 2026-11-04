import csv
import logging
from datetime import date
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CategoryForm, CustomUserCreationForm, ProductForm, SaleForm, SaleItemFormSet
from .models import Category, Product, Sale, SaleItem

logger = logging.getLogger(__name__)


def staff_only(view_func):
    @wraps(view_func)
    @login_required
    @user_passes_test(lambda user: user.is_staff, login_url='dashboard')
    def _wrapped(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return _wrapped


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

    top_items = SaleItem.objects.values('product__name', 'product__sku').annotate(
        total_quantity=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price_at_sale')),
    ).order_by('-total_quantity')[:5]

    reorder_recommendations = Product.objects.filter(
        stock_quantity__lte=F('low_stock_threshold')
    ).select_related('category').order_by('stock_quantity')[:5]

    context = {
        'total_products': Product.objects.count(),
        'total_sales_overall': Sale.objects.count(),
        'total_sales_value_overall': Sale.objects.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
        'inventory_value': inventory_value,
        'low_stock_products': low_stock_products[:8],
        'low_stock_count': low_stock_products.count(),
        'reorder_recommendations': reorder_recommendations,
        'recent_products': Product.objects.select_related('category').order_by('-created_at')[:5],
        'recent_sales': Sale.objects.select_related('user').order_by('-sale_date')[:5],
        'total_monthly_sales_count': monthly_stats['count'] or 0,
        'total_monthly_sales_amount': monthly_stats['amount'] or Decimal('0.00'),
        'top_items': top_items,
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


@staff_only
def export_products_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="smartinv_products.csv"'
    writer = csv.writer(response)
    writer.writerow(['name', 'sku', 'category', 'price', 'stock_quantity', 'low_stock_threshold'])
    for product in Product.objects.select_related('category').order_by('name'):
        writer.writerow([
            product.name,
            product.sku,
            product.category.name if product.category else '',
            format(product.price, '.2f'),
            product.stock_quantity,
            product.low_stock_threshold,
        ])
    return response


@staff_only
def export_sales_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="smartinv_sales.csv"'
    writer = csv.writer(response)
    writer.writerow(['sale_id', 'sale_date', 'recorded_by', 'total_amount'])
    for sale in Sale.objects.select_related('user').order_by('-sale_date'):
        writer.writerow([
            sale.pk,
            sale.sale_date.strftime('%Y-%m-%d %H:%M:%S'),
            sale.user.get_full_name() or sale.user.username,
            format(sale.total_amount, '.2f'),
        ])
    return response


@staff_only
def category_list(request):
    categories = Category.objects.order_by('name')
    return render(request, 'categories/category_list.html', {
        'categories': categories,
        'title': 'Categories',
    })


@staff_only
def add_category(request):
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        category = form.save()
        messages.success(request, f'Category “{category.name}” created.')
        return redirect('category_list')
    return render(request, 'categories/category_form.html', {
        'form': form,
        'title': 'Add Category',
    })


@staff_only
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        category = form.save()
        messages.success(request, f'Category “{category.name}” updated.')
        return redirect('category_list')
    return render(request, 'categories/category_form.html', {
        'form': form,
        'category': category,
        'title': 'Edit Category',
    })


@staff_only
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted.')
        return redirect('category_list')
    return render(request, 'categories/category_confirm_delete.html', {
        'category': category,
        'title': 'Delete Category',
    })


@staff_only
def low_stock_alerts(request):
    products = Product.objects.filter(
        stock_quantity__lte=F('low_stock_threshold')
    ).select_related('category').order_by('stock_quantity', 'name')
    context = {
        'products': products,
        'title': 'Low Stock Alerts',
    }
    return render(request, 'alerts/low_stock.html', context)


@staff_only
def send_low_stock_alerts(request):
    products = Product.objects.filter(stock_quantity__lte=F('low_stock_threshold')).select_related('category')
    message = []
    for product in products:
        message.append(f'{product.name} ({product.sku}): {product.stock_quantity} left; reorder threshold {product.low_stock_threshold}.')
    if not products:
        message.append('No low-stock items at this time.')
    if request.method == 'POST':
        if hasattr(request, 'user') and getattr(request.user, 'email', None):
            from django.core.mail import send_mail
            send_mail(
                'SmartInvent low-stock alert',
                '\n'.join(message),
                'noreply@smartinv.local',
                [request.user.email],
                fail_silently=True,
            )
            messages.success(request, 'Low-stock alert email sent.')
        else:
            messages.warning(request, 'No email is configured for this user. Alert preview shown on screen.')
        return redirect('low_stock_alerts')
    return render(request, 'alerts/low_stock_preview.html', {'message': '\n'.join(message), 'title': 'Low Stock Alert Preview'})


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


@staff_only
def sales_analytics(request):
    current = timezone.now().replace(day=1)
    monthly_trend = []
    max_value = Decimal('0.01')
    months = []

    for offset in range(5, -1, -1):
        month_start = current.replace(month=((current.month - offset - 1) % 12) + 1, year=current.year + ((current.month - offset - 1) // 12))
        month_label = month_start.strftime('%b %Y')
        month_total = Sale.objects.filter(
            sale_date__year=month_start.year,
            sale_date__month=month_start.month,
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        months.append((month_label, float(month_total)))
        if month_total > max_value:
            max_value = month_total

    for label, value in months:
        monthly_trend.append({
            'label': label,
            'value': value,
            'percentage': round((value / max_value) * 100 if max_value else 0, 1),
        })

    top_products = SaleItem.objects.values('product__name', 'product__sku').annotate(
        total_quantity=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price_at_sale')),
    ).order_by('-total_quantity')[:5]

    totals = Sale.objects.aggregate(
        total_revenue=Sum('total_amount'),
        total_orders=Count('id'),
    )
    avg_order_value = (totals['total_revenue'] / totals['total_orders']) if totals['total_orders'] else Decimal('0.00')

    context = {
        'monthly_trend': monthly_trend,
        'top_products': top_products,
        'total_revenue': totals['total_revenue'] or Decimal('0.00'),
        'total_orders': totals['total_orders'] or 0,
        'average_order_value': avg_order_value,
        'title': 'Sales Analytics',
    }
    return render(request, 'reports/analytics.html', context)


@staff_only
def sales_report(request):
    sales = Sale.objects.select_related('user').order_by('-sale_date')
    context = {
        'sales': sales,
        'title': 'Sales Report',
    }
    return render(request, 'reports/sales_report.html', context)
