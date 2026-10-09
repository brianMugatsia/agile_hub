from django import forms
from decimal import Decimal

from .models import CommissionSetting


class CommissionSettingForm(forms.ModelForm):
    rate = forms.DecimalField(
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=5,
        decimal_places=2,
        label="Rate (%)",
        help_text="Enter a percentage from 0 to 100, such as 20 for 20%.",
        widget=forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
    )

    class Meta:
        model = CommissionSetting
        fields = ("rate", "effective_from")
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_rate(self):
        return self.cleaned_data["rate"] / Decimal("100")