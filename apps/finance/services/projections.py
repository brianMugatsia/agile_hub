from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

CENT = Decimal("0.01")


@dataclass(frozen=True)
class ProjectionPeriod:
    period: int
    revenue: Decimal
    expenses: Decimal
    net_result: Decimal


def build_projection(
    *,
    starting_revenue,
    starting_expenses,
    revenue_growth_rate=Decimal("0"),
    expense_growth_rate=Decimal("0"),
    periods=12,
):
    revenue = Decimal(starting_revenue)
    expenses = Decimal(starting_expenses)
    revenue_growth_rate = Decimal(revenue_growth_rate)
    expense_growth_rate = Decimal(expense_growth_rate)
    if revenue < 0 or expenses < 0:
        raise ValidationError("Starting revenue and expenses cannot be negative.")
    if revenue_growth_rate < -1 or expense_growth_rate < -1:
        raise ValidationError("Growth rates cannot be less than -100%.")
    if isinstance(periods, bool) or not isinstance(periods, int) or not 1 <= periods <= 60:
        raise ValidationError({"periods": "Choose between 1 and 60 monthly periods."})

    result = []
    for period in range(1, periods + 1):
        revenue = (revenue * (1 + revenue_growth_rate)).quantize(CENT, rounding=ROUND_HALF_UP)
        expenses = (expenses * (1 + expense_growth_rate)).quantize(CENT, rounding=ROUND_HALF_UP)
        result.append(
            ProjectionPeriod(
                period=period,
                revenue=revenue,
                expenses=expenses,
                net_result=(revenue - expenses).quantize(CENT, rounding=ROUND_HALF_UP),
            )
        )
    return result