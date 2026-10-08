from datetime import date, datetime, time, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Case, F, IntegerField, Sum, Value, When
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView, View

from apps.commissions.models import SalesAgentCommission
from apps.commissions.services import approve_commission
from apps.core.scoping import scope_queryset
from apps.inventory.models import InventoryTransaction
from apps.payroll.models import SalaryRecord
from apps.payroll.services import approve_salary
from apps.sales.models import Sale, SaleItem


class ReportIndexView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "reports/index.html"
    permission_required = "accounts.export_reports"
    page_title = "Reports"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        context["report_links"] = [
            ("Sales", "sales:list"),
            ("Inventory", "inventory:list"),
            ("Commissions", "commissions:list"),
            ("Payroll", "payroll:salary_list"),
            ("Cash flow", "finance:cash_flow"),
            ("Audit trail", "audit:list"),
            ("Sales / stock reconciliation", "reports:inventory_reconciliation"),
        ]
        return context


class InventoryReconciliationView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "reports/inventory_reconciliation.html"
    permission_required = ("sales.view_sale", "inventory.view_inventorytransaction")
    page_title = "Sales / stock reconciliation"
    max_range_days = 366

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        start_value = self.request.GET.get("start", "")
        end_value = self.request.GET.get("end", "")
        errors = []

        def parse_date(value):
            if not value:
                return None
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError
                return parsed
            except (TypeError, ValueError):
                return None

        start_date = parse_date(start_value)
        end_date = parse_date(end_value)
        if start_value and start_date is None:
            errors.append("Enter a valid start date.")
        if end_value and end_date is None:
            errors.append("Enter a valid end date.")
        if not start_value and not end_value:
            start_date = today - timedelta(days=29)
            end_date = today
        elif start_date and not end_date:
            end_date = today
        elif end_date and not start_date:
            start_date = end_date
        if start_date and end_date:
            if end_date < start_date:
                errors.append("The end date must be on or after the start date.")
            elif (end_date - start_date).days + 1 > self.max_range_days:
                errors.append(f"Choose a date range of no more than {self.max_range_days} days.")

        mismatches = []
        if not errors:
            start_at = timezone.make_aware(datetime.combine(start_date, time.min))
            end_at = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
            sales = scope_queryset(
                Sale.objects.filter(
                    status__in=(Sale.Status.COMPLETED, Sale.Status.REFUNDED),
                    completed_at__gte=start_at,
                    completed_at__lt=end_at,
                ),
                self.request.user,
            )
            sale_rows = list(
                SaleItem.objects.filter(sale__in=sales)
                .values(
                    "sale_id",
                    "sale__hub_id",
                    "sale__hub__name",
                    "sale__status",
                    "product_id",
                    "product__name",
                )
                .annotate(quantity=Sum("quantity"))
            )
            sale_ids = {str(row["sale_id"]) for row in sale_rows}
            movement_rows = []
            if sale_ids:
                movements = scope_queryset(
                    InventoryTransaction.objects.filter(
                        kind__in=(InventoryTransaction.Kind.SALE, InventoryTransaction.Kind.REFUND),
                        reference__in=sale_ids,
                    ),
                    self.request.user,
                )
                movement_rows = list(
                    movements.values(
                        "hub_id", "hub__name", "product_id", "product__name", "reference"
                    )
                    .annotate(
                        outgoing=Sum(Case(
                            When(direction=InventoryTransaction.Direction.OUT, then=F("quantity")),
                            default=Value(0),
                            output_field=IntegerField(),
                        )),
                        incoming=Sum(Case(
                            When(direction=InventoryTransaction.Direction.IN, then=F("quantity")),
                            default=Value(0),
                            output_field=IntegerField(),
                        )),
                    )
                )
            actual = {
                (row["hub_id"], row["product_id"], row["reference"]): (
                    row["outgoing"] - row["incoming"],
                    row["hub__name"],
                    row["product__name"],
                )
                for row in movement_rows
            }
            expected_keys = set()
            for row in sale_rows:
                key = (row["sale__hub_id"], row["product_id"], str(row["sale_id"]))
                expected_keys.add(key)
                expected = (
                    0 if row["sale__status"] == Sale.Status.REFUNDED else row["quantity"]
                )
                actual_quantity = actual.get(key, (0, "", ""))[0]
                if expected != actual_quantity:
                    mismatches.append({
                        "sale_id": row["sale_id"],
                        "hub": row["sale__hub__name"],
                        "product": row["product__name"],
                        "expected": expected,
                        "recorded": actual_quantity,
                    })
            for key, (recorded, hub_name, product_name) in actual.items():
                if key not in expected_keys and recorded:
                    mismatches.append({
                        "sale_id": key[2],
                        "hub": hub_name,
                        "product": product_name,
                        "expected": 0,
                        "recorded": recorded,
                    })

        context.update(
            page_title=self.page_title,
            start_date=start_date,
            end_date=end_date,
            date_errors=errors,
            mismatches=mismatches[:1000],
            mismatch_count=len(mismatches),
            result_limit=1000,
        )
        return context


class ApprovalInboxView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "reports/approval_inbox.html"
    permission_required = (
        "payroll.approve_salaryrecord",
        "commissions.approve_salesagentcommission",
    )
    page_title = "Approval inbox"

    def has_permission(self):
        return any(
            self.request.user.has_perm(permission)
            for permission in self.get_permission_required()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        can_approve_salary = user.has_perm("payroll.approve_salaryrecord")
        can_approve_commission = user.has_perm("commissions.approve_salesagentcommission")
        context.update(
            page_title=self.page_title,
            can_approve_salary=can_approve_salary,
            can_approve_commission=can_approve_commission,
            pending_salaries=(
                scope_queryset(
                    SalaryRecord.objects.select_related("worker__user", "worker__hub"),
                    user,
                ).filter(status=SalaryRecord.Status.PENDING)
                if can_approve_salary
                else SalaryRecord.objects.none()
            ),
            pending_commissions=(
                scope_queryset(
                    SalesAgentCommission.objects.select_related("agent", "sale__hub"),
                    user,
                ).filter(status=SalesAgentCommission.Status.PENDING)
                if can_approve_commission
                else SalesAgentCommission.objects.none()
            ),
        )
        return context


class ApprovalActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    service = None
    id_argument = ""
    permission_required = ""
    success_message = "Record approved."

    def post(self, request, pk):
        try:
            self.service(**{self.id_argument: pk, "actor": request.user})
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, self.success_message)
        return redirect("reports:approvals")


class ApproveInboxSalaryView(ApprovalActionView):
    service = staticmethod(approve_salary)
    id_argument = "salary_id"
    permission_required = "payroll.approve_salaryrecord"
    success_message = "Salary approved."


class ApproveInboxCommissionView(ApprovalActionView):
    service = staticmethod(approve_commission)
    id_argument = "commission_id"
    permission_required = "commissions.approve_salesagentcommission"
    success_message = "Commission approved."