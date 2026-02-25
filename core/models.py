from django.conf import settings
from django.db import models
from django.utils import timezone

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
    stock_quantity = models.IntegerField(default=0)
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU/Code")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Define stock thresholds
    LOW_STOCK_THRESHOLD = 5

    class Meta:
        ordering = ['name'] # Order products by name by default

    def __str__(self):
        return self.name

    def get_stock_status(self):
        """
        Returns the stock status based on quantity.
        """
        if self.stock_quantity == 0:
            return "Out of Stock"
        elif self.stock_quantity < self.LOW_STOCK_THRESHOLD:
            return "Low Stock"
        else:
            return "In Stock"

    def is_low_stock(self):
        """
        Checks if the product is low stock for highlighting.
        """
        return self.stock_quantity > 0 and self.stock_quantity < self.LOW_STOCK_THRESHOLD

    def decrease_stock(self, quantity):
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            self.save()
            return True
        return False # Not enough stock

    def increase_stock(self, quantity):
        self.stock_quantity += quantity
        self.save()





class Sale(models.Model):
    # A sale belongs to a user (who made the sale, or who is the customer)
    # Using settings.AUTH_USER_MODEL for flexibility with custom user models later
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    sale_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # You could add customer info here if sales are tied to specific customers
    # customer_name = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ['-sale_date'] # Order sales by most recent first

    def __str__(self):
        return f"Sale #{self.id} on {self.sale_date.strftime('%Y-%m-%d %H:%M')}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT) # Don't delete product if part of a sale
    quantity = models.IntegerField(default=1)
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2) # Price when sold

    class Meta:
        unique_together = ('sale', 'product')
        verbose_name = "Sale Item"
        verbose_name_plural = "Sale Items"

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Sale #{self.sale.id}"

    def save(self, *args, **kwargs):
        # Capture product price at the time of sale if not already set
        if not self.price_at_sale:
            self.price_at_sale = self.product.price
        super().save(*args, **kwargs)

   