from django.conf import settings
from django.db import models, transaction
from django.core.exceptions import ValidationError


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)  # Changed to Positive
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU/Code")
    low_stock_threshold = models.PositiveIntegerField(default=5)  # Dynamic threshold
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [models.Index(fields=['sku'])]  # Faster lookups for security/audits

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def is_low_stock(self):
        return 0 < self.stock_quantity <= self.low_stock_threshold


class Sale(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)  # Protect user data
    sale_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['-sale_date']

    def update_total(self):
        """Calculates total amount based on related SaleItems."""
        total = sum(item.quantity * item.price_at_sale for item in self.items.all())
        self.total_amount = total
        self.save()


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    class Meta:
        unique_together = ('sale', 'product')

    def save(self, *args, **kwargs):

        with transaction.atomic():
            if not self.pk:  # Only on creation
                if self.product.stock_quantity < self.quantity:
                    raise ValidationError(f"Insufficient stock for {self.product.name}")

                # Update Product Stock
                self.product.stock_quantity -= self.quantity
                self.product.save()

                # Set price snapshot
                self.price_at_sale = self.product.price

            super().save(*args, **kwargs)
            self.sale.update_total()