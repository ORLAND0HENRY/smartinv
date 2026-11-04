from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product

User = get_user_model()


class CategoryAndLowStockTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username='manager', password='Strong-pass-123', is_staff=True)
        self.user = User.objects.create_user(username='cashier', password='Strong-pass-123')
        self.category = Category.objects.create(name='Office')
        self.product = Product.objects.create(
            name='Notebook', category=self.category, price=15, stock_quantity=2,
            sku='BOOK-002', low_stock_threshold=5,
        )

    def test_non_staff_is_redirected_from_category_list(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('category_list'))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_create_category(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('add_category'), {'name': 'Supplies', 'description': 'Office supplies'})
        self.assertRedirects(response, reverse('category_list'))
        self.assertTrue(Category.objects.filter(name='Supplies').exists())

    def test_low_stock_alerts_page_lists_problem_items(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('low_stock_alerts'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notebook')
        self.assertContains(response, '2')
