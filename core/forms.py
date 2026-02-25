
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import inlineformset_factory
from .models import Product, Category, Sale, SaleItem
from django.forms import BaseInlineFormSet
from django.core.exceptions import ValidationError

class BaseSaleItemFormSet(BaseInlineFormSet):
    def clean(self):
        """Checks for duplicate products in the same sale."""
        super().clean()
        if any(self.errors):
            return

        products = []
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            product = form.cleaned_data.get('product')
            if product in products:
                raise ValidationError(f"You have listed {product} more than once.")
            products.append(product)

class ProductForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        empty_label="Select a Category",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    price = forms.DecimalField(widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    stock_quantity = forms.IntegerField(widget=forms.NumberInput(attrs={'class': 'form-control'}))
    sku = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))

    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'stock_quantity', 'sku', 'description']

class CustomUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['username', 'password', 'password2']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale

        fields = []

# New Sale Item Form
class SaleItemForm(forms.ModelForm):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(stock_quantity__gt=0).order_by('name'),
        empty_label="Select Product",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantity'})
    )

    class Meta:
        model = SaleItem
        fields = ['product', 'quantity']

# Define the Sale Item Formset
SaleItemFormSet = inlineformset_factory(
    Sale,
    SaleItem,
    form=SaleItemForm,
    formset=BaseSaleItemFormSet,
    extra=1,
    can_delete=True,
    fields=['product', 'quantity']
)