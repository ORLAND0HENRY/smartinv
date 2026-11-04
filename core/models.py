from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from django.db.models import DecimalField


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=50, unique=True, verbose_name='SKU/Code')
    low_stock_threshold = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [models.Index(fields=['sku'])]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name='product_price_positive'),
        ]

    def __str__(self):
        return f'{self.name} ({self.sku})'

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold


class Sale(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    sale_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['-sale_date']

    def update_total(self):
        total = self.items.aggregate(
            total=Coalesce(
                Sum(F('quantity') * F('price_at_sale')),
                0,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )['total']
        self.total_amount = total
        self.save(update_fields=['total_amount'])


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sale', 'product'], name='unique_product_per_sale'),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='sale_item_quantity_positive'),
        ]

    @property
    def subtotal(self):
        return self.quantity * self.price_at_sale

    def save(self, *args, **kwargs):
        if self.pk:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            # A conditional update makes stock deduction safe against concurrent sales.
            updated = Product.objects.filter(
                pk=self.product_id,
                stock_quantity__gte=self.quantity,
            ).update(stock_quantity=F('stock_quantity') - self.quantity)
            if not updated:
                available = Product.objects.filter(pk=self.product_id).values_list(
                    'stock_quantity', flat=True,
                ).first()
                if available is None:
                    raise ValidationError('The selected product no longer exists.')
                raise ValidationError(
                    f'Insufficient stock for {self.product.name}. Only {available} units are available.'
                )
            self.price_at_sale = Product.objects.values_list('price', flat=True).get(pk=self.product_id)
            super().save(*args, **kwargs)
            self.sale.update_total()
