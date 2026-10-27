from django import forms
from decimal import Decimal

from .models import CommissionSetting


class CommissionSettingForm(forms.ModelForm):
    sales_agent_rate = forms.DecimalField(
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=5,
        decimal_places=2,
        label="Sales Agents & Members Rate (%)",
        initial=Decimal("0"),
        required=False,
        widget=forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
    )
    internal_provider_rate = forms.DecimalField(
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=5,
        decimal_places=2,
        label="Internal Service Providers Rate (%)",
        initial=Decimal("0"),
        required=False,
        widget=forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
    )
    external_provider_rate = forms.DecimalField(
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=5,
        decimal_places=2,
        label="External Service Providers Rate (%)",
        initial=Decimal("0"),
        required=False,
        widget=forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
    )

    class Meta:
        model = CommissionSetting
        fields = ("sales_agent_rate", "internal_provider_rate", "external_provider_rate", "effective_from")
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_sales_agent_rate(self):
        val = self.cleaned_data.get("sales_agent_rate")
        return (val / Decimal("100")) if val is not None else Decimal("0")

    def clean_internal_provider_rate(self):
        val = self.cleaned_data.get("internal_provider_rate")
        return (val / Decimal("100")) if val is not None else Decimal("0")

    def clean_external_provider_rate(self):
        val = self.cleaned_data.get("external_provider_rate")
        return (val / Decimal("100")) if val is not None else Decimal("0")
