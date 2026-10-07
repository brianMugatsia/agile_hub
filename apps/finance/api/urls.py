from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.finance.models import (
    Asset,
    CashFlow,
    EquityRecord,
    FundingSource,
    IncomeStatement,
    IncomeStatementItem,
    Liability,
    Projection,
    RevenueStream,
    StartupCost,
)

router = DefaultRouter()
for model, route, basename in (
    (Asset, "assets", "asset"),
    (CashFlow, "cash-flow", "cash-flow"),
    (EquityRecord, "equity", "equity"),
    (FundingSource, "funding-sources", "funding-source"),
    (IncomeStatement, "income-statements", "income-statement"),
    (IncomeStatementItem, "income-statement-items", "income-statement-item"),
    (Liability, "liabilities", "liability"),
    (Projection, "projections", "projection"),
    (RevenueStream, "revenue-streams", "revenue-stream"),
    (StartupCost, "startup-costs", "startup-cost"),
):
    register_readonly(router, model, route, basename)

urlpatterns = router.urls