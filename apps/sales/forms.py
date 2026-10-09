from django import forms

from apps.hubs.models import Hub
from apps.products.models import Product
from apps.beneficiaries.models import Business
from .models import Sale


class SaleEntryForm(forms.Form):
    hub = forms.ModelChoiceField(queryset=Hub.objects.filter(status=Hub.Status.ACTIVE))
    business = forms.ModelChoiceField(queryset=Business.objects.filter(status=Business.Status.ACTIVE), required=False)
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_active=True))
    quantity = forms.IntegerField(min_value=1)
    customer_name = forms.CharField(max_length=160, required=False)
    customer_phone = forms.CharField(max_length=24, required=False)
    payment_method = forms.ChoiceField(choices=[
        ("CASH", "Cash"),
        ("MOBILE_MONEY", "Mobile money"),
        ("BANK", "Bank transfer"),
        ("CREDIT", "Credit"),
    ])
    payment_reference = forms.CharField(max_length=80, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)


class SaleUpdateForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ("customer_name", "customer_phone", "payment_reference", "notes")