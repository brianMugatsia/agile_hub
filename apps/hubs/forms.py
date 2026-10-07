from django import forms

from .models import Hub


class HubForm(forms.ModelForm):
    class Meta:
        model = Hub
        fields = ["code", "name", "region", "address", "phone_number", "manager", "status"]
        widgets = {
            "address": forms.TextInput(attrs={"autocomplete": "street-address"}),
        }