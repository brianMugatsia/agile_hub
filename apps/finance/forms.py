from django import forms
from decimal import Decimal

from .models import CashFlow


class CashFlowForm(forms.ModelForm):
    class Meta:
        model = CashFlow
        fields = [
            "direction", "category", "amount", "transaction_date", "hub",
            "business", "reference", "description",
        ]
        widgets = {"transaction_date": forms.DateInput(attrs={"type": "date"})}


class BreakEvenForm(forms.Form):
    fixed_costs = forms.DecimalField(
        min_value=Decimal("0.00"), max_digits=14, decimal_places=2,
        label="Fixed costs per period",
    )
    selling_price = forms.DecimalField(
        min_value=Decimal("0.01"), max_digits=12, decimal_places=2,
        label="Selling price per unit",
    )
    variable_cost_per_unit = forms.DecimalField(
        min_value=Decimal("0.00"), max_digits=12, decimal_places=2,
        label="Variable cost per unit",
    )


class ProjectionForm(forms.Form):
    starting_revenue = forms.DecimalField(
        min_value=Decimal("0.00"), max_digits=14, decimal_places=2,
        label="Starting monthly revenue",
    )
    starting_expenses = forms.DecimalField(
        min_value=Decimal("0.00"), max_digits=14, decimal_places=2,
        label="Starting monthly expenses",
    )
    revenue_growth_percent = forms.DecimalField(
        min_value=Decimal("-100"), max_digits=7, decimal_places=2,
        initial=Decimal("0"), label="Monthly revenue growth (%)",
    )
    expense_growth_percent = forms.DecimalField(
        min_value=Decimal("-100"), max_digits=7, decimal_places=2,
        initial=Decimal("0"), label="Monthly expense growth (%)",
    )
    periods = forms.IntegerField(min_value=1, max_value=60, initial=12, label="Months to project")