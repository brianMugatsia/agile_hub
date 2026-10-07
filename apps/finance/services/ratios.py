from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError


def calculate_financial_ratios(*, total_assets, total_liabilities, total_equity):
    assets = Decimal(total_assets)
    liabilities = Decimal(total_liabilities)
    equity = Decimal(total_equity)
    if assets < 0 or liabilities < 0:
        raise ValidationError("Assets and liabilities cannot be negative.")
    debt_to_assets = (
        (liabilities / assets).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if assets > 0
        else None
    )
    liabilities_to_equity = (
        (liabilities / equity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if equity > 0
        else None
    )
    return {
        "debt_to_assets": debt_to_assets,
        "liabilities_to_equity": liabilities_to_equity,
    }