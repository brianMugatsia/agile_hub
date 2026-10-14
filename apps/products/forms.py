from django import forms

from apps.hubs.models import Hub
from apps.hubs.permissions import hubs_for_user
from .models import Product


class ProductForm(forms.ModelForm):
    initial_stock = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        label="Initial stock",
        help_text="Optional opening stock quantity for this product.",
    )
    hub = forms.ModelChoiceField(
        queryset=Hub.objects.none(),
        required=False,
        label="Stock Hub",
        help_text="Hub where initial stock should be recorded.",
    )

    class Meta:
        model = Product
        fields = [
            "sku", "name", "category", "description", "unit",
            "cost_price", "selling_price", "reorder_level", "is_active",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["hub"].queryset = hubs_for_user(user, active_only=True)
            user_hub = getattr(user, "hub", None)
            if user_hub and not self.instance.pk:
                self.fields["hub"].initial = user_hub


class ProductUpdateForm(ProductForm):
    price_change_reason = forms.CharField(
        max_length=255,
        required=False,
        label="Price change reason",
        help_text="Optional note recorded when the selling price changes.",
    )
