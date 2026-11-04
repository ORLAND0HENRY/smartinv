from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product

User = get_user_model()


class StaffAccessAndExportTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username='manager', password='Strong-pass-123', is_staff=True)
        self.user = User.objects.create_user(username='cashier', password='Strong-pass-123')
        self.category = Category.objects.create(name='Office')
        Product.objects.create(name='Notebook', category=self.category, price=15, stock_quantity=12, sku='BOOK-001', low_stock_threshold=3)

    def test_non_staff_user_is_redirected_from_analytics(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('sales_analytics'))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_view_analytics(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('sales_analytics'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sales analytics')
        self.assertContains(response, 'Monthly revenue trend')

    def test_staff_can_export_product_csv(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('export_products_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertContains(response, 'name,sku,category,price,stock_quantity,low_stock_threshold')

    def test_staff_can_export_sales_csv(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('export_sales_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sale_id,sale_date,recorded_by,total_amount')
