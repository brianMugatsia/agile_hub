import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Case, F, IntegerField, Q, Sum, Value, When
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView, View
from openpyxl import Workbook

from apps.commissions.models import SalesAgentCommission
from apps.commissions.services import approve_commission
from apps.core.scoping import scope_queryset
from apps.hubs.permissions import selected_hub
from apps.inventory.models import InventoryTransaction
from apps.payroll.models import SalaryRecord
from apps.payroll.services import approve_salary
from apps.products.models import Product
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
            ("Gross margins", "reports:gross_margins"),
        ]
        return context


class InventoryReconciliationView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "reports/inventory_reconciliation.html"
    permission_required = "sales.view_sale"
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
        available_hubs, chosen_hub, hub_error = selected_hub(self.request)
        if hub_error:
            errors.append(hub_error)
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
        check_count = 0
        matched_count = 0
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
            if chosen_hub:
                sales = sales.filter(hub=chosen_hub)
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
            movement_period = Q(created_at__gte=start_at, created_at__lt=end_at)
            if sale_ids:
                movement_period |= Q(reference__in=sale_ids)
            movements = scope_queryset(
                InventoryTransaction.objects.filter(
                    kind__in=(InventoryTransaction.Kind.SALE, InventoryTransaction.Kind.REFUND),
                ).filter(movement_period),
                self.request.user,
            )
            if chosen_hub:
                movements = movements.filter(hub=chosen_hub)
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
            sale_totals = {}
            for row in sale_rows:
                key = (row["sale__hub_id"], row["product_id"], str(row["sale_id"]))
                qty = row["quantity"] if row["sale__status"] == Sale.Status.COMPLETED else -row["quantity"]
                existing_qty, h_name, p_name = sale_totals.get(key, (0, row["sale__hub__name"], row["product__name"]))
                sale_totals[key] = (existing_qty + qty, h_name, p_name)

            expected_keys = set()
            for key, (sold_qty, h_name, p_name) in sale_totals.items():
                expected_keys.add(key)
                check_count += 1
                movement_qty, mov_h_name, mov_p_name = actual.get(key, (0, "", ""))
                hub_name = mov_h_name or h_name or "Hub"
                product_name = mov_p_name or p_name or f"Product #{key[1]}"
                if movement_qty == sold_qty:
                    matched_count += 1
                else:
                    mismatches.append({
                        "sale_id": key[2],
                        "hub": hub_name,
                        "product": product_name,
                        "expected": sold_qty,
                        "recorded": movement_qty,
                        "variance": movement_qty - sold_qty,
                        "issue": "Missing stock movement" if movement_qty < sold_qty else "Excess stock movement",
                    })

            for key, (recorded, hub_name, product_name) in actual.items():
                if key not in expected_keys and recorded:
                    check_count += 1
                    mismatches.append({
                        "sale_id": key[2],
                        "hub": hub_name or "Hub",
                        "product": product_name or f"Product #{key[1]}",
                        "expected": 0,
                        "recorded": recorded,
                        "variance": recorded,
                        "issue": "Unmatched stock movement",
                    })
            matched_count = check_count - len(mismatches)

        context.update(
            page_title=self.page_title,
            filter_hubs=available_hubs,
            selected_hub=chosen_hub.pk if chosen_hub else "",
            start_date=start_date,
            end_date=end_date,
            date_errors=errors,
            mismatches=mismatches[:1000],
            mismatch_count=len(mismatches),
            check_count=check_count,
            matched_count=matched_count,
            result_limit=1000,
            hub_error=hub_error,
        )
        return context


class GrossMarginsReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "reports/gross_margins_report.html"
    permission_required = "sales.view_sale"
    page_title = "Gross Margins"
    max_range_days = 366

    def get(self, request, *args, **kwargs):
        file_format = request.GET.get("format")
        if file_format in ("csv", "xlsx"):
            return self.export(request, file_format)
        return super().get(request, *args, **kwargs)

    def get_queryset_data(self, request):
        today = timezone.localdate()
        start_value = request.GET.get("start", "")
        end_value = request.GET.get("end", "")
        product_id = request.GET.get("product", "")
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
        available_hubs, chosen_hub, hub_error = selected_hub(request)
        if hub_error:
            errors.append(hub_error)
        if not start_value and not end_value:
            start_date = today - timedelta(days=29)
            end_date = today
        elif start_date and not end_date:
            end_date = today
        elif end_date and not start_date:
            start_date = end_date

        start_at = timezone.make_aware(datetime.combine(start_date, time.min))
        end_at = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))

        sales = scope_queryset(
            Sale.objects.filter(
                status=Sale.Status.COMPLETED,
                completed_at__gte=start_at,
                completed_at__lt=end_at,
            ),
            request.user,
        )
        if chosen_hub:
            sales = sales.filter(hub=chosen_hub)

        items_qs = SaleItem.objects.filter(sale__in=sales)
        if product_id:
            items_qs = items_qs.filter(product_id=product_id)

        rows = list(
            items_qs.values("product_id", "product__sku", "product__name")
            .annotate(
                total_qty=Sum("quantity"),
                total_revenue=Sum(F("quantity") * F("unit_price")),
                total_cost=Sum(F("quantity") * F("unit_cost")),
            )
            .order_by("product__name")
        )

        processed = []
        tot_rev = Decimal("0.00")
        tot_cost = Decimal("0.00")
        tot_qty = 0
        for r in rows:
            rev = r["total_revenue"] or Decimal("0.00")
            cost = r["total_cost"] or Decimal("0.00")
            margin = rev - cost
            margin_pct = (margin / rev * Decimal("100.00")) if rev > 0 else Decimal("0.00")
            tot_rev += rev
            tot_cost += cost
            tot_qty += r["total_qty"]
            processed.append({
                "product_sku": r["product__sku"],
                "product_name": r["product__name"],
                "quantity": r["total_qty"],
                "revenue": rev,
                "cost": cost,
                "margin_amount": margin,
                "margin_pct": margin_pct.quantize(Decimal("0.1")),
            })
        tot_margin = tot_rev - tot_cost
        tot_margin_pct = (tot_margin / tot_rev * Decimal("100.00")) if tot_rev > 0 else Decimal("0.00")
        totals = {
            "quantity": tot_qty,
            "revenue": tot_rev,
            "cost": tot_cost,
            "margin_amount": tot_margin,
            "margin_pct": tot_margin_pct.quantize(Decimal("0.1")),
        }
        return processed, totals, start_date, end_date, chosen_hub, errors

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows, totals, start_date, end_date, chosen_hub, errors = self.get_queryset_data(self.request)
        context.update({
            "rows": rows,
            "totals": totals,
            "start_date": start_date,
            "end_date": end_date,
            "chosen_hub": chosen_hub,
            "errors": errors,
            "products": Product.objects.filter(is_active=True).order_by("name"),
            "selected_product": self.request.GET.get("product", ""),
        })
        return context

    def export(self, request, file_format):
        rows, totals, start_date, end_date, chosen_hub, errors = self.get_queryset_data(request)
        headers = ["Product SKU", "Product Name", "Quantity Sold", "Revenue", "Cost", "Gross Margin", "Margin %"]
        data = [
            [
                r["product_sku"],
                r["product_name"],
                r["quantity"],
                str(r["revenue"]),
                str(r["cost"]),
                str(r["margin_amount"]),
                f"{r['margin_pct']}%",
            ]
            for r in rows
        ]
        data.append([
            "TOTALS",
            "",
            totals["quantity"],
            str(totals["revenue"]),
            str(totals["cost"]),
            str(totals["margin_amount"]),
            f"{totals['margin_pct']}%",
        ])

        if file_format == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="gross-margins-report.csv"'
            writer = csv.writer(response)
            writer.writerow(headers)
            for row in data:
                writer.writerow(row)
            return response
        else:
            wb = Workbook()
            ws = wb.active
            ws.title = "Gross Margins"
            ws.append(headers)
            for row in data:
                ws.append(row)
            output = BytesIO()
            wb.save(output)
            response = HttpResponse(
                output.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = 'attachment; filename="gross-margins-report.xlsx"'
            return response


class ApprovalInboxView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "reports/approval_inbox.html"
    permission_required = ("commissions.approve_salesagentcommission", "payroll.approve_salaryrecord")
    page_title = "Approval inbox"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        available_hubs, chosen_hub, hub_error = selected_hub(self.request)
        hubs = available_hubs
        if chosen_hub:
            hubs = hubs.filter(pk=chosen_hub.pk)
        elif hub_error:
            hubs = hubs.none()

        commissions = scope_queryset(
            SalesAgentCommission.objects.filter(
                status=SalesAgentCommission.Status.PENDING,
                sale__hub__in=hubs,
            ),
            self.request.user,
        ).select_related("agent", "sale", "sale__hub").order_by("-created_at")

        salaries = scope_queryset(
            SalaryRecord.objects.filter(
                status=SalaryRecord.Status.PENDING,
                worker__hub__in=hubs,
            ),
            self.request.user,
        ).select_related("worker", "worker__user", "worker__hub").order_by("-created_at")

        context.update(
            commissions=commissions,
            salaries=salaries,
            pending_commissions=commissions,
            pending_salaries=salaries,
            can_approve_salary=self.request.user.has_perm("payroll.approve_salaryrecord"),
            can_approve_commission=self.request.user.has_perm("commissions.approve_salesagentcommission"),
            available_hubs=available_hubs,
            filter_hubs=available_hubs,
            chosen_hub=chosen_hub,
            selected_hub=chosen_hub.pk if chosen_hub else "",
            hub_error=hub_error,
        )
        return context


class ApproveInboxCommissionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "commissions.approve_salesagentcommission"

    def post(self, request, pk):
        action = request.POST.get("action", "approve")
        try:
            if action == "reject":
                from apps.commissions.services import reject_commission
                reject_commission(commission_id=pk, actor=request.user, notes=request.POST.get("notes", ""))
                messages.success(request, "Commission rejected.")
            else:
                approve_commission(commission_id=pk, actor=request.user)
                messages.success(request, "Commission approved.")
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        return redirect("reports:approvals")


class ApproveInboxSalaryView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "payroll.approve_salaryrecord"

    def post(self, request, pk):
        action = request.POST.get("action", "approve")
        try:
            if action == "reject":
                from apps.payroll.services import reject_salary
                reject_salary(salary_id=pk, actor=request.user, notes=request.POST.get("notes", ""))
                messages.success(request, "Salary record rejected.")
            else:
                approve_salary(salary_id=pk, actor=request.user)
                messages.success(request, "Salary record approved.")
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        return redirect("reports:approvals")
