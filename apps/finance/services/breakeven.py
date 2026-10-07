from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.core.exceptions import ValidationError

CENT = Decimal("0.01")


def calculate_break_even(*, fixed_costs, selling_price, variable_cost_per_unit):
    fixed_costs = Decimal(fixed_costs)
    selling_price = Decimal(selling_price)
    variable_cost_per_unit = Decimal(variable_cost_per_unit)
    if fixed_costs < 0 or variable_cost_per_unit < 0:
        raise ValidationError("Costs cannot be negative.")
    if selling_price <= 0:
        raise ValidationError({"selling_price": "Selling price must be greater than zero."})
    contribution = selling_price - variable_cost_per_unit
    if contribution <= 0:
        raise ValidationError(
            {"variable_cost_per_unit": "Variable cost must be lower than the selling price."}
        )
    units = int((fixed_costs / contribution).to_integral_value(rounding=ROUND_CEILING))
    revenue = (selling_price * units).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"units": units, "revenue": revenue, "contribution_per_unit": contribution}