from django.contrib import admin

from .models import (
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


@admin.register(CashFlow)
class CashFlowAdmin(admin.ModelAdmin):
    list_display = ("transaction_date", "direction", "category", "amount", "hub", "business")
    list_filter = ("direction", "category", "transaction_date", "hub")
    search_fields = ("category", "reference", "description")


@admin.register(IncomeStatement)
class IncomeStatementAdmin(admin.ModelAdmin):
    list_display = ("period_start", "period_end", "business", "hub", "status", "prepared_by")
    list_filter = ("status", "period_start", "hub")
    inlines = []


for model in (Asset, EquityRecord, FundingSource, IncomeStatementItem, Liability, Projection, RevenueStream, StartupCost):
    admin.site.register(model)