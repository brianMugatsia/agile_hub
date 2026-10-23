from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from apps.finance.models import FinancialSetting

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


def get_active_financial_setting(day=None):
    day = day or timezone.localdate()
    setting = FinancialSetting.objects.filter(is_active=True, effective_from__lte=day).first()
    if setting:
        return setting
    class DefaultSetting:
        default_commission_rate = Decimal("0.20")
        internal_commission_rate = Decimal("0.20")
        external_commission_rate = Decimal("0.20")
        default_sales_expense_rate = Decimal("0.05")
        sales_expense_calculation_basis = "NET_REVENUE"
        commission_calculation_basis = "PROFIT_BEFORE_COMMISSION"
        provider_dormancy_days = Decimal("90.00")
    return DefaultSetting()


def calculate_net_revenue(*, gross_revenue, returns=Decimal("0.00"), discounts=Decimal("0.00")):
    gross = Decimal(gross_revenue or 0)
    ret = Decimal(returns or 0)
    disc = Decimal(discounts or 0)
    return max(Decimal("0.00"), (gross - ret - disc)).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_gross_profit(*, net_revenue, direct_service_costs=Decimal("0.00")):
    net = Decimal(net_revenue or 0)
    costs = Decimal(direct_service_costs or 0)
    return max(Decimal("0.00"), (net - costs)).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_sales_expense(*, base_amount, rate=None, basis="NET_REVENUE"):
    setting = get_active_financial_setting()
    r = Decimal(rate) if rate is not None else setting.default_sales_expense_rate
    base = Decimal(base_amount or 0)
    return (base * r).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_profit_before_commission(*, gross_profit, operating_expenses=Decimal("0.00")):
    gp = Decimal(gross_profit or 0)
    opex = Decimal(operating_expenses or 0)
    return max(Decimal("0.00"), (gp - opex)).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_service_provider_commission(*, base_amount, rate=None, provider_type="INTERNAL"):
    setting = get_active_financial_setting()
    if rate is not None:
        r = Decimal(rate)
    elif provider_type == "INTERNAL":
        r = setting.internal_commission_rate
    else:
        r = setting.external_commission_rate
    base = Decimal(base_amount or 0)
    return (base * r).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_net_hub_profit(*, profit_before_commission, provider_commission=Decimal("0.00")):
    pbc = Decimal(profit_before_commission or 0)
    comm = Decimal(provider_commission or 0)
    return max(Decimal("0.00"), (pbc - comm)).quantize(CENT, rounding=ROUND_HALF_UP)
