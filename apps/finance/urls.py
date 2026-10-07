from django.urls import path

from .views import (
    AssetListView,
    BreakEvenView,
    CashFlowCreateView,
    CashFlowListView,
    EquityListView,
    FinancialOverviewView,
    FinancialRatiosView,
    FundingSourcesListView,
    LiabilityListView,
    ProjectionCalculatorView,
    StartupCostsListView,
)

app_name = "finance"

urlpatterns = [
    path("", FinancialOverviewView.as_view(), name="income_statement"),
    path("cash-flow/", CashFlowListView.as_view(), name="cash_flow"),
    path("cash-flow/create/", CashFlowCreateView.as_view(), name="cash_flow_create"),
    path("assets/", AssetListView.as_view(), name="assets"),
    path("liabilities/", LiabilityListView.as_view(), name="liabilities"),
    path("equity/", EquityListView.as_view(), name="equity"),
    path("startup-costs/", StartupCostsListView.as_view(), name="startup_costs"),
    path("funding-sources/", FundingSourcesListView.as_view(), name="funding_sources"),
    path("break-even/", BreakEvenView.as_view(), name="break_even"),
    path("projections/", ProjectionCalculatorView.as_view(), name="projections"),
    path("ratios/", FinancialRatiosView.as_view(), name="ratios"),
]