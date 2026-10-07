from django import forms

from apps.hubs.models import Hub
from apps.products.models import Product

from .models import InventoryTransaction


class StockMovementForm(forms.Form):
    hub = forms.ModelChoiceField(queryset=Hub.objects.filter(status=Hub.Status.ACTIVE))
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_active=True))
    kind = forms.ChoiceField(choices=[
        (InventoryTransaction.Kind.RECEIPT, "Receive stock"),
        (InventoryTransaction.Kind.ISSUE, "Issue stock"),
        (InventoryTransaction.Kind.ADJUSTMENT, "Adjust stock"),
    ])
    quantity = forms.IntegerField(min_value=1)
    direction = forms.ChoiceField(choices=InventoryTransaction.Direction.choices, required=False)
    unit_cost = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    reference = forms.CharField(max_length=80, required=False)
    notes = forms.CharField(max_length=255, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") == InventoryTransaction.Kind.ADJUSTMENT and not cleaned.get("direction"):
            self.add_error("direction", "Choose whether this adjustment adds or removes stock.")
        return cleaned