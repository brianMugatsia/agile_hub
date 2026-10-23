from decimal import Decimal
import pytest
from apps.finance.services.calculations import (
    calculate_net_revenue,
    calculate_gross_profit,
    calculate_sales_expense,
    calculate_profit_before_commission,
    calculate_service_provider_commission,
    calculate_net_hub_profit,
)

pytestmark = pytest.mark.django_db


def test_financial_calculations():
    net_rev = calculate_net_revenue(gross_revenue=Decimal("1000.00"), returns=Decimal("50.00"), discounts=Decimal("20.00"))
    assert net_rev == Decimal("930.00")

    gp = calculate_gross_profit(net_revenue=Decimal("930.00"), direct_service_costs=Decimal("300.00"))
    assert gp == Decimal("630.00")

    sales_exp = calculate_sales_expense(base_amount=Decimal("930.00"), rate=Decimal("0.05"))
    assert sales_exp == Decimal("46.50")

    pbc = calculate_profit_before_commission(gross_profit=Decimal("630.00"), operating_expenses=Decimal("130.00"))
    assert pbc == Decimal("500.00")

    comm = calculate_service_provider_commission(base_amount=Decimal("500.00"), rate=Decimal("0.20"), provider_type="INTERNAL")
    assert comm == Decimal("100.00")

    net_profit = calculate_net_hub_profit(profit_before_commission=Decimal("500.00"), provider_commission=Decimal("100.00"))
    assert net_profit == Decimal("400.00")
