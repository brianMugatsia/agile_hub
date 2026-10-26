from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError


def calculate_financial_ratios(*, total_assets, total_liabilities, total_equity, net_income=Decimal("0.00")):
    assets = Decimal(total_assets)
    liabilities = Decimal(total_liabilities)
    equity = Decimal(total_equity)
    net_inc = Decimal(net_income)

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
    debt_to_equity = liabilities_to_equity

    equity_multiplier = (
        (assets / equity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if equity > 0
        else None
    )

    roa = (
        (net_inc / assets).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if assets > 0
        else None
    )

    roe = (
        (net_inc / equity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if equity > 0
        else None
    )

    risk_level = "Unavailable"
    risk_badge_class = "badge--neutral"
    if debt_to_assets is not None:
        if debt_to_assets < Decimal("0.40"):
            risk_level = "Strong / Low Risk"
            risk_badge_class = "badge--success"
        elif debt_to_assets <= Decimal("0.70"):
            risk_level = "Moderate Leverage"
            risk_badge_class = "badge--warning"
        else:
            risk_level = "High Financial Risk"
            risk_badge_class = "badge--danger"

    return {
        "debt_to_assets": debt_to_assets,
        "liabilities_to_equity": liabilities_to_equity,
        "debt_to_equity": debt_to_equity,
        "equity_multiplier": equity_multiplier,
        "roa": roa,
        "roe": roe,
        "risk_level": risk_level,
        "risk_badge_class": risk_badge_class,
    }
