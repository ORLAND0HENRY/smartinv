from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Product, Sale, SaleItem

User = get_user_model()


class BootstrapFormMixin:
    """Apply consistent Bootstrap form styles without discarding widget classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {css_class}'.strip()
            if field.required:
                field.widget.attrs.setdefault('aria-required', 'true')


class ProductForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'stock_quantity', 'sku', 'low_stock_threshold']
        widgets = {
            'price': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}),
            'stock_quantity': forms.NumberInput(attrs={'min': 0}),
            'low_stock_threshold': forms.NumberInput(attrs={'min': 0}),
        }

    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise ValidationError('Price must be greater than zero.')
        return price


class CustomUserCreationForm(BootstrapFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')


class SaleForm(BootstrapFormMixin, forms.ModelForm):
    customer_name = forms.CharField(
        max_length=100,
        required=False,
        help_text='Optional: Record customer name for reference',
    )

    class Meta:
        model = Sale
        fields = []


class BaseSaleItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        products = set()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            product = form.cleaned_data.get('product')
            quantity = form.cleaned_data.get('quantity')
            if not product or not quantity:
                continue
            if product.pk in products:
                raise ValidationError(f'Product “{product.name}” can only appear once per sale.')
            products.add(product.pk)
            if product.stock_quantity < quantity:
                raise ValidationError(
                    f'Only {product.stock_quantity} units of {product.name} are currently available.'
                )
        if not products:
            raise ValidationError('Add at least one product to the sale.')


SaleItemFormSet = inlineformset_factory(
    Sale,
    SaleItem,
    fields=['product', 'quantity'],
    extra=1,
    can_delete=True,
    formset=BaseSaleItemFormSet,
    widgets={
        'product': forms.Select(attrs={'class': 'product-select'}),
        'quantity': forms.NumberInput(attrs={'min': 1, 'class': 'quantity-input'}),
    },
)
