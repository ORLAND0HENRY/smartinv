from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, Sale, SaleItem

User = get_user_model()


class InventoryAndSalesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cashier', password='Strong-pass-123')
        self.category = Category.objects.create(name='Stationery')
        self.product = Product.objects.create(
            name='Notebook', category=self.category, price=Decimal('12.50'),
            stock_quantity=8, sku='NOTE-001', low_stock_threshold=3,
        )

    def grant(self, codename):
        permission = Permission.objects.get(codename=codename)
        self.user.user_permissions.add(permission)

    def test_sale_deducts_stock_and_freezes_price(self):
        sale = Sale.objects.create(user=self.user)
        SaleItem.objects.create(sale=sale, product=self.product, quantity=3)
        self.product.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertEqual(sale.total_amount, Decimal('37.50'))
        self.product.price = Decimal('20.00')
        self.product.save()
        self.assertEqual(sale.items.get().price_at_sale, Decimal('12.50'))

    def test_sale_cannot_oversell(self):
        sale = Sale.objects.create(user=self.user)
        with self.assertRaisesMessage(Exception, 'Insufficient stock'):
            SaleItem.objects.create(sale=sale, product=self.product, quantity=9)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)
        self.assertFalse(sale.items.exists())

    def test_inventory_search_filters_by_sku(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('product_list'), {'q': 'NOTE-001'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notebook')
        self.assertContains(response, 'NOTE-001')

    def test_product_mutation_requires_permission_and_post(self):
        self.client.force_login(self.user)
        url = reverse('delete_product', args=[self.product.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.grant('delete_product')
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.client.post(url)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_record_sale_updates_inventory_atomically(self):
        self.grant('add_sale')
        self.client.force_login(self.user)
        response = self.client.post(reverse('record_sale'), {
            'customer_name': '',
            'sale_items-TOTAL_FORMS': '1',
            'sale_items-INITIAL_FORMS': '0',
            'sale_items-MIN_NUM_FORMS': '0',
            'sale_items-MAX_NUM_FORMS': '1000',
            'sale_items-0-product': str(self.product.pk),
            'sale_items-0-quantity': '2',
        })
        self.assertRedirects(response, reverse('sale_list'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)
        self.assertEqual(Sale.objects.get().total_amount, Decimal('25.00'))

    def test_product_form_rejects_non_positive_price(self):
        self.grant('add_product')
        self.client.force_login(self.user)
        response = self.client.post(reverse('add_product'), {
            'name': 'Invalid', 'category': str(self.category.pk), 'price': '0',
            'stock_quantity': '1', 'sku': 'INVALID-1', 'low_stock_threshold': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Price must be greater than zero.')
        self.assertFalse(Product.objects.filter(sku='INVALID-1').exists())
