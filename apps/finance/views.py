from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import TemplateView, FormView

from apps.accounts.roles import Role
from apps.audit.services import record_event
from apps.core.generic import ProtectedCreateView, ProtectedUpdateView, ScopedModelListView, hubs_for_user
from apps.core.exports import ScopedModelExportView
from apps.core.mixins import PageMixin
from apps.core.scoping import scope_queryset
from apps.hubs.permissions import selected_hub
from apps.sales.models import Sale, SaleItem
from apps.members.models import Business

from .forms import BreakEvenForm, CashFlowForm, ExpenseForm, ProjectionForm, FinancialSettingForm
from .models import (
    Asset,
    CashFlow,
    EquityRecord,
    Expense,
    FundingSource,
    IncomeStatement,
    IncomeStatementItem,
    Liability,
    StartupCost,
    FinancialSetting,
    FinancialRateAudit,
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
        available_hubs, selected, hub_error = selected_hub(self.request)
        hub_ids = available_hubs.values_list("pk", flat=True)
        is_platform_admin = role in (Role.SUPER_ADMIN, Role.ADMIN)
        hub_scoped_roles = (Role.HUB_MANAGER, Role.FINANCE_OFFICER, Role.VIEWER)
        if role in hub_scoped_roles:
            sales = sales.filter(hub_id__in=hub_ids)
        elif role == Role.MEMBER:
            sales = sales.filter(business__member__user=self.request.user)
        elif not is_platform_admin:
            sales = sales.none()
        if selected:
            sales = sales.filter(hub=selected)
        elif hub_error:
            sales = sales.none()
        sales_revenue = _sum(sales, "total")
        businesses = Business.objects.filter(
            amount__gt=0,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        )
        if role in hub_scoped_roles:
            businesses = businesses.filter(hub_id__in=hub_ids)
        elif role == Role.MEMBER:
            businesses = businesses.filter(member__user=self.request.user)
        elif not is_platform_admin:
            businesses = businesses.none()
        if selected:
            businesses = businesses.filter(hub=selected)
        elif hub_error:
            businesses = businesses.none()
        member_contributions_total = _sum(businesses, "amount")
        revenue = sales_revenue + member_contributions_total
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
        elif role == Role.MEMBER or not is_platform_admin:
            salaries = salaries.none()
        if selected:
            salaries = salaries.filter(worker__hub=selected)
        elif hub_error:
            salaries = salaries.none()
        payroll = _sum(salaries, "gross_amount")

        expenses_qs = Expense.objects.filter(
            expense_date__gte=period_start,
            expense_date__lte=period_end,
        )
        if role in hub_scoped_roles:
            expenses_qs = expenses_qs.filter(
                Q(hub_id__in=hub_ids) | Q(business__hub_id__in=hub_ids)
            )
        elif role == Role.MEMBER:
            expenses_qs = expenses_qs.filter(business__member__user=self.request.user)
        elif not is_platform_admin:
            expenses_qs = expenses_qs.none()
        if selected:
            expenses_qs = expenses_qs.filter(
                Q(hub=selected) | Q(business__hub=selected)
            )
        elif hub_error:
            expenses_qs = expenses_qs.none()

        cogs_from_expenses = _sum(
            expenses_qs.filter(category=Expense.Category.STOCK_COST_OF_GOODS),
            "amount",
        )
        other_expenses_total = _sum(
            expenses_qs.exclude(category=Expense.Category.STOCK_COST_OF_GOODS),
            "amount",
        )
        cost_of_goods = cost_of_goods + cogs_from_expenses

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
        elif role == Role.MEMBER:
            expense_items = expense_items.filter(statement__business__member__user=self.request.user)
        elif not is_platform_admin:
            expense_items = expense_items.none()
        if selected:
            expense_items = expense_items.filter(
                Q(statement__hub=selected) | Q(statement__business__hub=selected)
            )
        elif hub_error:
            expense_items = expense_items.none()
        manual_expenses = _sum(
            expense_items,
            "amount",
        ) + other_expenses_total

        operating_expenses = commissions + payroll + manual_expenses
        total_expenses = cost_of_goods + operating_expenses
        context.update(
            page_title=self.page_title,
            period_start=period_start,
            period_end=period_end,
            filter_hubs=available_hubs,
            selected_hub=selected.pk if selected else "",
            hub_error=hub_error,
            sales_revenue=sales_revenue,
            member_contributions_total=member_contributions_total,
            revenue=revenue,
            cost_of_goods=cost_of_goods,
            gross_profit=revenue - cost_of_goods,
            commissions=commissions,
            payroll=payroll,
            manual_expenses=manual_expenses,
            operating_expenses=operating_expenses,
            total_expenses=total_expenses,
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
    filter_hub = True


class CashFlowCreateView(ProtectedCreateView):
    model = CashFlow
    form_class = CashFlowForm
    page_title = "Record cash flow"
    success_url_name = "finance:cash_flow"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        available_hubs = hubs_for_user(self.request.user)
        form.fields["hub"].queryset = available_hubs
        if self.request.user.role == "MEMBER":
            form.fields["business"].queryset = Business.objects.filter(
                member__user=self.request.user
            )
        else:
            form.fields["business"].queryset = Business.objects.filter(
                Q(hub__in=available_hubs) | Q(hub__isnull=True)
            ).select_related("member__user")
        return form


class ExpenseListView(ScopedModelListView):
    model = Expense
    page_title = "Expenses"
    template_name = "finance/expense_list.html"
    columns = (
        {"label": "Date", "field": "expense_date"},
        {"label": "Category", "field": "get_category_display"},
        {"label": "Title", "field": "title"},
        {"label": "Amount", "field": "amount"},
        {"label": "Hub", "field": "hub__name"},
        {"label": "Reference", "field": "reference"},
    )
    search_fields = ("title", "reference", "notes")
    create_url_name = "finance:expense_create"
    create_label = "Record expense"
    create_permission = "finance.add_expense"
    export_url_name = "finance:export"
    import_url_name = "finance:import"
    import_permission = "finance.add_expense"
    filter_hub = True
    filter_fields = (
        ("category", Expense.Category.choices),
    )
    date_filter_field = "expense_date"
    row_edit_url_name = "finance:expense_edit"
    row_edit_permission = "finance.change_expense"
    row_delete_url_name = "finance:expense_delete"
    row_delete_permission = "finance.delete_expense"


class ExpenseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "finance.delete_expense"

    def post(self, request, pk):
        expense = get_object_or_404(
            scope_queryset(Expense.objects.all(), request.user),
            pk=pk,
        )
        expense.delete()
        messages.success(request, "Expense deleted.")
        return redirect("finance:expenses")


class ExpenseExportView(ScopedModelExportView):
    list_view_class = ExpenseListView


class ExpenseCreateView(ProtectedCreateView):
    model = Expense
    form_class = ExpenseForm
    page_title = "Record expense"
    success_url_name = "finance:expenses"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        available_hubs = hubs_for_user(self.request.user)
        form.fields["hub"].queryset = available_hubs
        if self.request.user.role == "MEMBER":
            form.fields["business"].queryset = Business.objects.filter(     
                member__user=self.request.user
            )
        else:
            form.fields["business"].queryset = Business.objects.filter(     
                Q(hub__in=available_hubs) | Q(hub__isnull=True)
            ).select_related("member__user")
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        expense = self.object
        CashFlow.objects.create(
            hub=expense.hub,
            business=expense.business,
            direction=CashFlow.Direction.OUTFLOW,
            category=expense.get_category_display(),
            amount=expense.amount,
            transaction_date=expense.expense_date,
            reference=f"EXP-{expense.pk}",
            description=f"Auto-logged expense outflow: {expense.title}",
            created_by=self.request.user if self.request.user.is_authenticated else None,
        )
        return response

class ExpenseUpdateView(ProtectedUpdateView):
    model = Expense
    form_class = ExpenseForm
    page_title = "Edit expense"
    success_url_name = "finance:expenses"
    cancel_url_name = "finance:expenses"
    permission_required = "finance.change_expense"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        available_hubs = hubs_for_user(self.request.user)
        form.fields["hub"].queryset = available_hubs
        if self.request.user.role == "MEMBER":
            form.fields["business"].queryset = Business.objects.filter(
                member__user=self.request.user
            )
        else:
            form.fields["business"].queryset = Business.objects.filter(
                Q(hub__in=available_hubs) | Q(hub__isnull=True)
            ).select_related("member__user")
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
    filter_hub = True


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
    filter_hub = True


class EquityListView(ScopedModelListView):
    model = EquityRecord
    page_title = "Equity"
    columns = (
        {"label": "Record", "field": "name"},
        {"label": "Amount", "field": "amount"},
        {"label": "Date", "field": "transaction_date"},
    )
    filter_hub = True


class StartupCostsListView(ScopedModelListView):
    model = StartupCost
    page_title = "Startup costs"
    columns = (
        {"label": "Cost", "field": "name"},
        {"label": "Category", "field": "category"},
        {"label": "Amount", "field": "amount"},
        {"label": "Date", "field": "incurred_on"},
    )
    filter_hub = True


class FundingSourcesListView(ScopedModelListView):
    model = FundingSource
    page_title = "Funding sources"
    columns = (
        {"label": "Source", "field": "name"},
        {"label": "Type", "field": "source_type"},
        {"label": "Amount", "field": "amount"},
        {"label": "Received", "field": "received_on"},
    )
    filter_hub = True


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
        available_hubs, selected, hub_error = selected_hub(self.request)
        role = self.request.user.role
        hub_ids = available_hubs.values_list("pk", flat=True)
        is_platform_admin = role in (Role.SUPER_ADMIN, Role.ADMIN)
        hub_scoped_roles = (Role.HUB_MANAGER, Role.FINANCE_OFFICER, Role.VIEWER)

        assets = scope_queryset(Asset.objects.all(), self.request.user)
        liabilities = scope_queryset(Liability.objects.all(), self.request.user)
        equity = scope_queryset(EquityRecord.objects.all(), self.request.user)
        sales = Sale.objects.filter(status=Sale.Status.COMPLETED)
        businesses = Business.objects.filter(amount__gt=0)
        expenses_qs = Expense.objects.all()

        if role in hub_scoped_roles:
            sales = sales.filter(hub_id__in=hub_ids)
            businesses = businesses.filter(hub_id__in=hub_ids)
            expenses_qs = expenses_qs.filter(Q(hub_id__in=hub_ids) | Q(business__hub_id__in=hub_ids))
        elif role == Role.MEMBER:
            sales = sales.filter(business__member__user=self.request.user)
            businesses = businesses.filter(member__user=self.request.user)
            expenses_qs = expenses_qs.filter(business__member__user=self.request.user)
        elif not is_platform_admin:
            sales = sales.none()
            businesses = businesses.none()
            expenses_qs = expenses_qs.none()

        if selected:
            assets = assets.filter(Q(hub=selected) | Q(business__hub=selected))
            liabilities = liabilities.filter(Q(hub=selected) | Q(business__hub=selected))
            equity = equity.filter(Q(hub=selected) | Q(business__hub=selected))
            sales = sales.filter(hub=selected)
            businesses = businesses.filter(hub=selected)
            expenses_qs = expenses_qs.filter(Q(hub=selected) | Q(business__hub=selected))
        elif hub_error:
            assets, liabilities, equity, sales, businesses, expenses_qs = assets.none(), liabilities.none(), equity.none(), sales.none(), businesses.none(), expenses_qs.none()

        total_assets = _sum(assets, "cost")
        total_liabilities = _sum(liabilities, "balance")
        total_equity = _sum(equity, "amount")

        sales_rev = _sum(sales, "total")
        contrib_rev = _sum(businesses, "amount")
        total_rev = sales_rev + contrib_rev

        sale_items = SaleItem.objects.filter(sale__in=sales)
        cogs = _sum(
            sale_items,
            None,
            expression=ExpressionWrapper(
                F("quantity") * F("unit_cost"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        cogs_exp = _sum(expenses_qs.filter(category=Expense.Category.STOCK_COST_OF_GOODS), "amount")
        total_cogs = cogs + cogs_exp

        commissions_total = _sum(sales.filter(commission__status__in=["PENDING", "APPROVED", "PAID"]), "commission__amount")

        from apps.payroll.models import SalaryRecord
        salaries = SalaryRecord.objects.filter(status__in=[SalaryRecord.Status.PENDING, SalaryRecord.Status.APPROVED, SalaryRecord.Status.PAID])
        if role in hub_scoped_roles:
            salaries = salaries.filter(worker__hub_id__in=hub_ids)
        elif role == Role.MEMBER or not is_platform_admin:
            salaries = salaries.none()
        if selected:
            salaries = salaries.filter(worker__hub=selected)
        elif hub_error:
            salaries = salaries.none()
        payroll_total = _sum(salaries, "gross_amount")

        other_exp = _sum(expenses_qs.exclude(category=Expense.Category.STOCK_COST_OF_GOODS), "amount")

        net_income = total_rev - total_cogs - commissions_total - payroll_total - other_exp

        ratios = calculate_financial_ratios(
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            net_income=net_income,
        )
        context.update(
            page_title=self.page_title,
            filter_hubs=available_hubs,
            selected_hub=selected.pk if selected else "",
            hub_error=hub_error,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            net_income=net_income,
            ratios=ratios,
        )
        return context


class FinancialSettingsView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, FormView):
    template_name = "finance/settings.html"
    form_class = FinancialSettingForm
    permission_required = "finance.configure_financialsetting"
    page_title = "Financial & Commission Settings"

    def get_initial(self):
        latest = FinancialSetting.objects.filter(is_active=True).order_by("-effective_from").first()
        if latest:
            return {
                "default_commission_rate": latest.default_commission_rate,
                "internal_commission_rate": latest.internal_commission_rate,
                "external_commission_rate": latest.external_commission_rate,
                "default_sales_expense_rate": latest.default_sales_expense_rate,
                "sales_expense_calculation_basis": latest.sales_expense_calculation_basis,
                "commission_calculation_basis": latest.commission_calculation_basis,
                "provider_dormancy_days": latest.provider_dormancy_days,
                "effective_from": timezone.localdate(),
                "is_active": True,
            }
        return {"effective_from": timezone.localdate(), "is_active": True}

    def form_valid(self, form):
        current = FinancialSetting.objects.filter(is_active=True).order_by("-effective_from").first()
        new_setting = form.save(commit=False)
        new_setting.created_by = self.request.user
        new_setting.save()

        if current:
            fields_to_check = [
                ("default_commission_rate", current.default_commission_rate, new_setting.default_commission_rate),
                ("internal_commission_rate", current.internal_commission_rate, new_setting.internal_commission_rate),
                ("external_commission_rate", current.external_commission_rate, new_setting.external_commission_rate),
                ("default_sales_expense_rate", current.default_sales_expense_rate, new_setting.default_sales_expense_rate),
                ("provider_dormancy_days", current.provider_dormancy_days, new_setting.provider_dormancy_days),
            ]
            for fname, old_val, new_val in fields_to_check:
                if old_val != new_val:
                    FinancialRateAudit.objects.create(
                        setting_name=fname,
                        previous_value=str(old_val),
                        new_value=str(new_val),
                        changed_by=self.request.user,
                    )
        record_event(
            action="financial_settings.updated",
            summary=f"Financial settings updated by {self.request.user}",
            actor=self.request.user,
            target=new_setting,
        )
        messages.success(self.request, "Financial and commission settings successfully updated.")
        return redirect("finance:settings")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["audit_history"] = FinancialRateAudit.objects.order_by("-created_at")[:20]
        return context
