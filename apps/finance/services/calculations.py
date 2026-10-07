from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def sum_amounts(values):
    return sum((Decimal(value or 0) for value in values), Decimal("0.00")).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def net_cash_flow(*, inflows, outflows):
    return (Decimal(inflows) - Decimal(outflows)).quantize(CENT, rounding=ROUND_HALF_UP)


def gross_margin(*, revenue, cost_of_goods):
    revenue = Decimal(revenue)
    if revenue == 0:
        return None
    return ((revenue - Decimal(cost_of_goods)) / revenue).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )