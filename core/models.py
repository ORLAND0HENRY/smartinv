from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce


class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True)
    contact_person = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


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
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
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
                output_field=models.DecimalField(max_digits=12, decimal_places=2),
            )
        )['total'] or 0
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
            updated = Product.objects.filter(
                pk=self.product_id,
                stock_quantity__gte=self.quantity,
            ).update(stock_quantity=F('stock_quantity') - self.quantity)
            if not updated:
                available = Product.objects.filter(pk=self.product_id).values_list('stock_quantity', flat=True).first()
                if available is None:
                    raise ValueError('The selected product no longer exists.')
                raise ValueError(f'Insufficient stock for {self.product.name}. Only {available} units are available.')

            self.price_at_sale = Product.objects.values_list('price', flat=True).get(pk=self.product_id)
            super().save(*args, **kwargs)
            self.sale.update_total()


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('ordered', 'Ordered'),
        ('received', 'Received'),
    ]
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    order_date = models.DateTimeField(auto_now_add=True)
    expected_delivery = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ordered')
    notes = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['-order_date']

    def update_total(self):
        total = self.items.aggregate(
            total=Coalesce(
                Sum(F('quantity') * F('unit_cost')),
                0,
                output_field=models.DecimalField(max_digits=12, decimal_places=2),
            )
        )['total'] or 0
        self.total_amount = total
        self.save(update_fields=['total_amount'])

    def receive(self):
        if self.status == 'received':
            return
        with transaction.atomic():
            for item in self.items.select_related('product'):
                item.product.stock_quantity += item.quantity
                item.product.save()
            self.status = 'received'
            self.save(update_fields=['status'])


class PurchaseOrderItem(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_order_items')
    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order', 'product'], name='unique_order_product'),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='purchase_item_quantity_positive'),
            models.CheckConstraint(condition=models.Q(unit_cost__gt=0), name='purchase_item_cost_positive'),
        ]

    @property
    def subtotal(self):
        return self.quantity * self.unit_cost

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.order.update_total()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.order.update_total()


class StockAdjustment(models.Model):
    CHANGE_TYPE_CHOICES = [
        ('restock', 'Restock'),
        ('manual', 'Manual adjustment'),
        ('sale', 'Sale deduction'),
    ]
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_adjustments')
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPE_CHOICES, default='manual')
    quantity = models.IntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_adjustments')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name}: {self.quantity} ({self.change_type})'


class ProductAuditLog(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_audit_logs')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name}: {self.action}'


class ProductPhoto(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='product_photos/', blank=True, null=True)
    caption = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} photo'


class PurchaseOrderAudit(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_order_audit_logs')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order}: {self.action}'


class SupplierPerformance(models.Model):
    supplier = models.OneToOneField(Supplier, on_delete=models.CASCADE, related_name='performance')
    on_time_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    average_lead_time_days = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.supplier.name} performance'


class PurchaseOrderStatus(models.Model):
    order = models.OneToOneField(PurchaseOrder, on_delete=models.CASCADE, related_name='status_snapshot')
    status = models.CharField(max_length=20, default='ordered')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.order}: {self.status}'


class SupplierNote(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='notes')
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='supplier_notes')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.supplier.name} note'


class ReorderRecommendation(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='reorder_recommendation')
    recommended_quantity = models.PositiveIntegerField(default=0)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.product.name} reorder'


class InventoryMovement(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_movements')
    movement_type = models.CharField(max_length=20, choices=[('in', 'In'), ('out', 'Out')], default='in')
    quantity = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_movements')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} {self.movement_type}: {self.quantity}'


class SupplierCategory(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='supplier_categories')
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    class Meta:
        unique_together = ('supplier', 'category')

    def __str__(self):
        return f'{self.supplier.name} -> {self.category.name}'


class ProductSupplierQuote(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='quotes')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='quotes')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    valid_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.product.name} quote from {self.supplier.name}'


class SupplierRating(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='ratings')
    score = models.PositiveSmallIntegerField(default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.supplier.name} rating {self.score}'


class PriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.product.name}: {self.price}'


class PurchaseOrderLineItem(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='line_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'


class StockTransfer(models.Model):
    from_product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='transfers_out')
    to_product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='transfers_in')
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_transfers')

    def __str__(self):
        return f'{self.from_product} -> {self.to_product}'


class InventoryCheck(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_checks')
    expected_quantity = models.PositiveIntegerField(default=0)
    actual_quantity = models.PositiveIntegerField(default=0)
    variance = models.IntegerField(default=0)
    checked_at = models.DateTimeField(auto_now_add=True)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_checks')

    def __str__(self):
        return f'{self.product.name} variance {self.variance}'


class PurchaseRequest(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_requests')
    quantity = models.PositiveIntegerField(default=1)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.product.name} buy request'


class SupplierInvoice(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='invoices')
    invoice_number = models.CharField(max_length=100, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.invoice_number


class InventoryPolicy(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='policies')
    reorder_point = models.PositiveIntegerField(default=0)
    target_stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.product.name} inventory policy'


class ProductReturn(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='returns')
    quantity = models.PositiveIntegerField(default=1)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_returns')

    def __str__(self):
        return f'{self.product.name} return'


class SupplierContact(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.name


class ProductTag(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=50)

    class Meta:
        unique_together = ('product', 'name')

    def __str__(self):
        return self.name


class ProductBundle(models.Model):
    name = models.CharField(max_length=150)
    products = models.ManyToManyField(Product, related_name='bundles')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ProductComment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_comments')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.product.name} comment'


class OpenPurchaseOrder(models.Model):
    order = models.OneToOneField(PurchaseOrder, on_delete=models.CASCADE, related_name='open_order')
    pending_quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.order} open'


class SupplierPreference(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='preferences')
    preference = models.CharField(max_length=100)
    value = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f'{self.supplier.name}: {self.preference}'


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.product.name} image'


class PurchaseOrderInvoice(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='invoices')
    number = models.CharField(max_length=100, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.number
