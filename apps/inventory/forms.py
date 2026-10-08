from django import forms
from django.forms import ModelForm

from apps.hubs.models import Hub
from apps.hubs.permissions import hubs_for_user
from apps.products.models import Product

from .models import InventoryTransaction, PurchaseOrder, Supplier


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


class SupplierForm(ModelForm):
    class Meta:
        model = Supplier
        fields = ("code", "name", "contact_name", "email", "phone", "address")


class ReorderOrderForm(forms.Form):
    hub = forms.ModelChoiceField(queryset=Hub.objects.none())
    supplier = forms.ModelChoiceField(queryset=Supplier.objects.none())
    notes = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hub"].queryset = hubs_for_user(user, active_only=True)
        self.fields["supplier"].queryset = Supplier.objects.filter(is_active=True)


class PurchaseOrderReceiveForm(forms.Form):
    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order
        for line in order.lines.select_related("product").order_by("product__name"):
            self.fields[f"line_{line.pk}"] = forms.IntegerField(
                label=f"{line.product.name} (outstanding: {line.quantity_remaining})",
                min_value=0,
                max_value=line.quantity_remaining,
                initial=0,
                required=True,
            )

    def received_quantities(self):
        return {
            int(name.removeprefix("line_")): quantity
            for name, quantity in self.cleaned_data.items()
            if name.startswith("line_")
        }