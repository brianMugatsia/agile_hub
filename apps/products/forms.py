from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku", "name", "category", "description", "unit",
            "cost_price", "selling_price", "reorder_level", "is_active",
        ]


class ProductUpdateForm(ProductForm):
    price_change_reason = forms.CharField(
        max_length=255,
        required=False,
        label="Price change reason",
        help_text="Optional note recorded when the selling price changes.",
    )