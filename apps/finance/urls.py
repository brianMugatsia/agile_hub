from django.urls import path

from apps.core.spreadsheets import ExpenseImportTemplateView, ExpenseImportView
from .views import (
    AssetListView,
    BreakEvenView,
    CashFlowCreateView,
    CashFlowListView,
    EquityListView,
    ExpenseCreateView,
    ExpenseDeleteView,
    ExpenseExportView,
    ExpenseListView,
    ExpenseUpdateView,
    FinancialOverviewView,
    FinancialRatiosView,
    FundingSourcesListView,
    LiabilityListView,
    ProjectionCalculatorView,
    StartupCostsListView,
    FinancialSettingsView,
)

app_name = "finance"

urlpatterns = [
    path("", FinancialOverviewView.as_view(), name="income_statement"),
    path("settings/", FinancialSettingsView.as_view(), name="settings"),
    path("cash-flow/", CashFlowListView.as_view(), name="cash_flow"),
    path("cash-flow/create/", CashFlowCreateView.as_view(), name="cash_flow_create"),
    path("expenses/", ExpenseListView.as_view(), name="expenses"),
    path("expenses/create/", ExpenseCreateView.as_view(), name="expense_create"),
    path("expenses/<int:pk>/edit/", ExpenseUpdateView.as_view(), name="expense_edit"),
    path("expenses/<int:pk>/delete/", ExpenseDeleteView.as_view(), name="expense_delete"),
    path("expenses/import/", ExpenseImportView.as_view(), name="import"),
    path("expenses/import/template.xlsx", ExpenseImportTemplateView.as_view(), name="expense_import_template"),
    path("expenses/export/<str:file_format>/", ExpenseExportView.as_view(), name="export"),
    path("assets/", AssetListView.as_view(), name="assets"),
    path("liabilities/", LiabilityListView.as_view(), name="liabilities"),
    path("equity/", EquityListView.as_view(), name="equity"),
    path("startup-costs/", StartupCostsListView.as_view(), name="startup_costs"),
    path("funding-sources/", FundingSourcesListView.as_view(), name="funding_sources"),
    path("break-even/", BreakEvenView.as_view(), name="break_even"),
    path("projections/", ProjectionCalculatorView.as_view(), name="projections"),
    path("ratios/", FinancialRatiosView.as_view(), name="ratios"),
]
