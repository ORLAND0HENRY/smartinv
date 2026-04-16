from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import Product, Category, Sale, SaleItem

User = get_user_model()


class TailwindMixin:
    """Mixin to inject consistent amber-500 styling into form widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            existing_classes = field.widget.attrs.get('class', '')
            field.widget.attrs[
                'class'] = f"{existing_classes} block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-amber-500 sm:text-sm sm:leading-6".strip()


class ProductForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'stock_quantity', 'sku', 'low_stock_threshold']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class CustomUserCreationForm(TailwindMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class SaleForm(TailwindMixin, forms.ModelForm):
    customer_name = forms.CharField(
        max_length=100,
        required=False,
        help_text="Optional: Record customer name for reference"
    )

    class Meta:
        model = Sale
        fields = []  # user and date are handled automatically in the view


class BaseSaleItemFormSet(BaseInlineFormSet):
    def clean(self):
        """Checks for duplicate products and ensures at least one item is sold."""
        if any(self.errors):
            return

        products = []
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue

            product = form.cleaned_data.get('product')
            quantity = form.cleaned_data.get('quantity')

            if product:
                if product in products:
                    raise ValidationError(f"Product '{product.name}' is added multiple times.")
                products.append(product)

                # Check stock availability early in the form validation
                if product.stock_quantity < (quantity or 0):
                    raise ValidationError(f"Only {product.stock_quantity} units of {product.name} available.")

        if not products:
            raise ValidationError("You must add at least one product to the sale.")


# Create the FormSet for SaleItems
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
    }
)