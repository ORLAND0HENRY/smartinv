from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, PurchaseOrder, PurchaseOrderItem, Supplier

User = get_user_model()


class SupplierAndPurchaseOrderTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username='buyer', password='Strong-pass-123', is_staff=True)
        self.user = User.objects.create_user(username='cashier', password='Strong-pass-123')
        self.supplier = Supplier.objects.create(name='Acme Goods', contact_person='Jane Doe', email='jane@example.com', phone='0700123456')
        self.category = Category.objects.create(name='Office')
        self.product = Product.objects.create(
            name='Notebook', category=self.category, supplier=self.supplier,
            price=15, stock_quantity=2, sku='BOOK-555', low_stock_threshold=5,
        )

    def test_non_staff_is_redirected_from_supplier_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('supplier_list'))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_create_supplier(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('add_supplier'), {
            'name': 'Atlas Supplies',
            'contact_person': 'John',
            'email': 'john@atlas.com',
            'phone': '0712345678',
            'address': 'Nairobi',
        })
        self.assertRedirects(response, reverse('supplier_list'))
        self.assertTrue(Supplier.objects.filter(name='Atlas Supplies').exists())

    def test_receiving_purchase_order_adds_stock(self):
        self.client.force_login(self.staff)
        order = PurchaseOrder.objects.create(supplier=self.supplier, status='ordered')
        PurchaseOrderItem.objects.create(order=order, product=self.product, quantity=8, unit_cost=12.00)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
        self.client.post(reverse('receive_purchase_order', args=[order.pk]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        order.refresh_from_db()
        self.assertEqual(order.status, 'received')
