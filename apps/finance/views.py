from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import HttpResponseBadRequest
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import TemplateView

from apps.accounts.roles import Role
from apps.core.generic import ProtectedCreateView, ScopedModelListView, hubs_for_user
from apps.core.scoping import scope_queryset
from apps.sales.models import Sale, SaleItem

from .forms import BreakEvenForm, CashFlowForm, ProjectionForm
from .models import (
    Asset,
    CashFlow,
    EquityRecord,
    FundingSource,
    IncomeStatementItem,
    Liability,
    StartupCost,
)
from .services.breakeven import calculate_break_even
from .services.projections import build_projection
from .services.ratios import calculate_financial_ratios


def _sum(queryset, field, *, expression=None):
    target = expression if expression is not None else field
    value = queryset.aggregate(total=Sum(target))["total"]
    return value if value is not None else Decimal("0.00")


class FinancialOverviewView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "finance/income_statement.html"
    permission_required = "finance.view_incomestatement"
    page_title = "Income statement"

    def dispatch(self, request, *args, **kwargs):
        start_value = request.GET.get("start", "")
        end_value = request.GET.get("end", "")
        try:
            start = parse_date(start_value)
        except ValueError:
            start = None
        try:
            end = parse_date(end_value)
        except ValueError:
            end = None
        if start_value and (not start or start.isoformat() != start_value):
            return HttpResponseBadRequest("Use YYYY-MM-DD for the start date.")
        if end_value and (not end or end.isoformat() != end_value):
            return HttpResponseBadRequest("Use YYYY-MM-DD for the end date.")
        if start and end and end < start:
            return HttpResponseBadRequest("The end date must be on or after the start date.")
        if start and end and (end - start).days + 1 > 366:
            return HttpResponseBadRequest("Choose a date range of no more than 366 days.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        start_date = parse_date(self.request.GET.get("start", ""))
        end_date = parse_date(self.request.GET.get("end", ""))
        if start_date and not end_date:
            period_start = period_end = start_date
        elif end_date and not start_date:
            period_start = period_end = end_date
        else:
            period_start = start_date or today.replace(day=1)
            period_end = end_date or today

        sales = Sale.objects.filter(
            status=Sale.Status.COMPLETED,
            completed_at__date__gte=period_start,
            completed_at__date__lte=period_end,
        )
        role = self.request.user.role
        hub_ids = hubs_for_user(self.request.user).values_list("pk", flat=True)
        is_platform_admin = role in (Role.SUPER_ADMIN, Role.ADMIN)
        hub_scoped_roles = (Role.HUB_MANAGER, Role.FINANCE_OFFICER, Role.VIEWER)
        if role in hub_scoped_roles:
            sales = sales.filter(hub_id__in=hub_ids)
        elif role == Role.BENEFICIARY:
            sales = sales.filter(business__beneficiary__user=self.request.user)
        elif not is_platform_admin:
            sales = sales.none()
        revenue = _sum(sales, "total")
        sale_items = SaleItem.objects.filter(sale__in=sales)
        cost_of_goods = _sum(
            sale_items,
            None,
            expression=ExpressionWrapper(
                F("quantity") * F("unit_cost"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        commissions = _sum(
            sales.filter(commission__status__in=["PENDING", "APPROVED", "PAID"]),
            "commission__amount",
        )

        from apps.payroll.models import SalaryRecord

        salaries = SalaryRecord.objects.filter(
            period_start__lte=period_end,
            period_end__gte=period_start,
            status__in=[
                SalaryRecord.Status.PENDING,
                SalaryRecord.Status.APPROVED,
                SalaryRecord.Status.PAID,
            ],
        )
        if role in hub_scoped_roles:
            salaries = salaries.filter(worker__hub_id__in=hub_ids)
        elif role == Role.BENEFICIARY or not is_platform_admin:
            salaries = salaries.none()
        payroll = _sum(salaries, "gross_amount")
        expense_items = IncomeStatementItem.objects.filter(
            is_expense=True,
            statement__period_start__lte=period_end,
            statement__period_end__gte=period_start,
        )
        if role in hub_scoped_roles:
            expense_items = expense_items.filter(
                Q(statement__hub_id__in=hub_ids)
                | Q(statement__business__hub_id__in=hub_ids)
            )
        elif role == Role.BENEFICIARY:
            expense_items = expense_items.filter(statement__business__beneficiary__user=self.request.user)
        elif not is_platform_admin:
            expense_items = expense_items.none()
        manual_expenses = _sum(
            expense_items,
            "amount",
        )
        operating_expenses = commissions + payroll + manual_expenses
        context.update(
            page_title=self.page_title,
            period_start=period_start,
            period_end=period_end,
            revenue=revenue,
            cost_of_goods=cost_of_goods,
            gross_profit=revenue - cost_of_goods,
            commissions=commissions,
            payroll=payroll,
            manual_expenses=manual_expenses,
            operating_expenses=operating_expenses,
            net_profit=revenue - cost_of_goods - operating_expenses,
        )
        return context


class CashFlowListView(ScopedModelListView):
    model = CashFlow
    page_title = "Cash flow"
    columns = (
        {"label": "Date", "field": "transaction_date"},
        {"label": "Direction", "field": "direction"},
        {"label": "Category", "field": "category"},
        {"label": "Amount", "field": "amount"},
        {"label": "Hub", "field": "hub__name"},
        {"label": "Reference", "field": "reference"},
    )
    search_fields = ("category", "reference", "description")
    create_url_name = "finance:cash_flow_create"
    create_label = "Record cash flow"
    create_permission = "finance.add_cashflow"


class CashFlowCreateView(ProtectedCreateView):
    model = CashFlow
    form_class = CashFlowForm
    page_title = "Record cash flow"
    success_url_name = "finance:cash_flow"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["hub"].queryset = hubs_for_user(self.request.user)
        if self.request.user.role == "BENEFICIARY":
            form.fields["business"].queryset = form.fields["business"].queryset.filter(
                beneficiary__user=self.request.user
            )
        return form


class AssetListView(ScopedModelListView):
    model = Asset
    page_title = "Assets"
    columns = (
        {"label": "Asset", "field": "name"},
        {"label": "Category", "field": "category"},
        {"label": "Cost", "field": "cost"},
        {"label": "Acquired", "field": "acquisition_date"},
        {"label": "Hub", "field": "hub__name"},
    )
    search_fields = ("name", "category")


class LiabilityListView(ScopedModelListView):
    model = Liability
    page_title = "Liabilities"
    columns = (
        {"label": "Liability", "field": "name"},
        {"label": "Counterparty", "field": "counterparty"},
        {"label": "Balance", "field": "balance"},
        {"label": "Due", "field": "due_date"},
        {"label": "Hub", "field": "hub__name"},
    )
    search_fields = ("name", "counterparty")


class EquityListView(ScopedModelListView):
    model = EquityRecord
    page_title = "Equity"
    columns = (
        {"label": "Record", "field": "name"},
        {"label": "Amount", "field": "amount"},
        {"label": "Date", "field": "transaction_date"},
    )


class StartupCostsListView(ScopedModelListView):
    model = StartupCost
    page_title = "Startup costs"
    columns = (
        {"label": "Cost", "field": "name"},
        {"label": "Category", "field": "category"},
        {"label": "Amount", "field": "amount"},
        {"label": "Date", "field": "incurred_on"},
    )


class FundingSourcesListView(ScopedModelListView):
    model = FundingSource
    page_title = "Funding sources"
    columns = (
        {"label": "Source", "field": "name"},
        {"label": "Type", "field": "source_type"},
        {"label": "Amount", "field": "amount"},
        {"label": "Received", "field": "received_on"},
    )


class BreakEvenView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "finance/break_even.html"
    permission_required = "finance.view_incomestatement"
    page_title = "Break-even estimate"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = BreakEvenForm(self.request.GET if "calculate" in self.request.GET else None)
        result = None
        if form.is_bound and form.is_valid():
            try:
                result = calculate_break_even(**form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
        context.update(page_title=self.page_title, form=form, result=result)
        return context


class ProjectionCalculatorView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "finance/projections.html"
    permission_required = "finance.view_incomestatement"
    page_title = "Financial projections"
    columns = (
        {"label": "Month", "field": "period"},
        {"label": "Revenue", "field": "revenue"},
        {"label": "Expenses", "field": "expenses"},
        {"label": "Net result", "field": "net_result"},
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = ProjectionForm(self.request.GET if "calculate" in self.request.GET else None)
        periods = []
        if form.is_bound and form.is_valid():
            values = form.cleaned_data
            try:
                periods = build_projection(
                    starting_revenue=values["starting_revenue"],
                    starting_expenses=values["starting_expenses"],
                    revenue_growth_rate=values["revenue_growth_percent"] / Decimal("100"),
                    expense_growth_rate=values["expense_growth_percent"] / Decimal("100"),
                    periods=values["periods"],
                )
            except ValidationError as error:
                form.add_error(None, error)
        context.update(page_title=self.page_title, form=form, periods=periods, columns=self.columns)
        return context


class FinancialRatiosView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "finance/ratios.html"
    permission_required = "finance.view_incomestatement"
    page_title = "Financial ratios"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_assets = _sum(scope_queryset(Asset.objects.all(), self.request.user), "cost")
        total_liabilities = _sum(
            scope_queryset(Liability.objects.all(), self.request.user), "balance"
        )
        total_equity = _sum(scope_queryset(EquityRecord.objects.all(), self.request.user), "amount")
        context.update(
            page_title=self.page_title,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            ratios=calculate_financial_ratios(
                total_assets=total_assets,
                total_liabilities=total_liabilities,
                total_equity=total_equity,
            ),
        )
        return context