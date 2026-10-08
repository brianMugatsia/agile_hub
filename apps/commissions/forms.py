from django import forms

from .models import CommissionSetting


class CommissionSettingForm(forms.ModelForm):
    class Meta:
        model = CommissionSetting
        fields = ("rate", "effective_from")
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "rate": forms.NumberInput(attrs={"min": "0", "max": "1", "step": "0.0001"}),
        }