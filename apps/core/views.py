from datetime import date, datetime, time, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.conf import settings
from django.db.models import F, Sum
from django.db import models
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.roles import Role
from apps.hubs.permissions import selected_hub
from .mixins import PageMixin


class LandingPageView(TemplateView):
    template_name = "landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            page_title="Agile Hub",
            contact_email=settings.PUBLIC_CONTACT_EMAIL,
            contact_phone=settings.PUBLIC_CONTACT_PHONE,
            contact_location=settings.PUBLIC_CONTACT_LOCATION,
        )
        return context


class DashboardView(LoginRequiredMixin, PageMixin, TemplateView):
    """Renders the dashboard template that matches the signed-in user's role."""

    page_title = "Dashboard"
    max_date_range_days = 366

    def get_date_range(self):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        start_value = self.request.GET.get("start_date", "")
        end_value = self.request.GET.get("end_date", "")
        errors = []

        def parse_date(value, field_name):
            if not value:
                return None
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError
                return parsed
            except (TypeError, ValueError):
                errors.append(f"Enter a valid {field_name} date in YYYY-MM-DD format.")
                return None

        start_date = parse_date(start_value, "start")
        end_date = parse_date(end_value, "end")

        if not start_value and not end_value:
            start_date, end_date = month_start, month_end
        elif start_date and not end_value:
            end_date = start_date
        elif end_date and not start_value:
            start_date = end_date

        if not errors and start_date and end_date:
            if end_date < start_date:
                errors.append("The end date must be the same as or later than the start date.")
            elif (end_date - start_date).days + 1 > self.max_date_range_days:
                errors.append(
                    f"Choose a date range of no more than {self.max_date_range_days} days."
                )

        if errors:
            start_date, end_date = month_start, month_end
        return start_date, end_date, errors

    def apply_date_range(self, queryset, field_name):
        start_date, end_date = self.date_range
        field = queryset.model._meta.get_field(field_name)
        if isinstance(field, models.DateTimeField):
            start_at = timezone.make_aware(datetime.combine(start_date, time.min))
            end_at = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
            return queryset.filter(**{f"{field_name}__gte": start_at, f"{field_name}__lt": end_at})
        return queryset.filter(**{f"{field_name}__range": (start_date, end_date)})

    def get_template_names(self):
        return [f"dashboard/{self.request.user.role.lower()}.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        start_date, end_date, date_errors = self.get_date_range()
        self.date_range = start_date, end_date
        context.update(
            date_start=start_date,
            date_end=end_date,
            date_errors=date_errors,
        )
        from apps.commissions.models import SalesAgentCommission
        from apps.hubs.models import Hub
        from apps.inventory.models import InventoryBalance
        from apps.payroll.models import SalaryRecord
        from apps.products.models import Product
        from apps.sales.models import Sale
        from apps.core.generic import hubs_for_user

        is_platform_admin = user.role in (Role.SUPER_ADMIN, Role.ADMIN)
        available_hubs, active_hub, hub_error = selected_hub(self.request)
        hubs = available_hubs
        if active_hub:
            hubs = hubs.filter(pk=active_hub.pk)
        elif hub_error:
            hubs = hubs.none()
        sales = Sale.objects.filter(status=Sale.Status.COMPLETED)
        if is_platform_admin:
            context["dashboard_intro"] = (
                "A live overview of hubs, products, completed sales and commission activity."
            )
        elif user.role in (Role.HUB_MANAGER, Role.FINANCE_OFFICER, Role.VIEWER):
            sales = sales.filter(hub__in=hubs)
        elif user.role == Role.SALES_AGENT:
            sales = sales.filter(agent=user)
        elif user.role == Role.BENEFICIARY:
            sales = sales.filter(business__beneficiary__user=user)
        else:
            sales = sales.none()
        if active_hub:
            sales = sales.filter(hub=active_hub)
        elif hub_error:
            sales = sales.none()
        sales = self.apply_date_range(sales, "completed_at")

        if not is_platform_admin:
            context["dashboard_intro"] = {
                Role.HUB_MANAGER: "Recent sales, stock levels and approvals for your hubs.",
                Role.FINANCE_OFFICER: "Recent sales and outstanding payment approvals for your hubs.",
                Role.SALES_AGENT: "Your completed sales and commission activity.",
                Role.WORKER: "Your salary records and payment history.",
                Role.BENEFICIARY: "Your businesses and associated sales activity.",
                Role.VIEWER: "A read-only summary of activity at your hubs.",
            }.get(user.role, "Your latest Agile Hub activity.")

        context["recent_sales"] = sales.select_related("hub", "agent").order_by("-completed_at")[:8]
        context["sales_columns"] = (
            {"label": "Date", "field": "completed_at"},
            {"label": "Hub", "field": "hub__name"},
            {"label": "Agent", "field": "agent__display_name"},
            {"label": "Customer", "field": "customer_name"},
            {"label": "Total", "field": "total"},
            {"label": "Status", "field": "status"},
        )

        if is_platform_admin or user.role in (Role.HUB_MANAGER, Role.FINANCE_OFFICER, Role.VIEWER):
            balances = InventoryBalance.objects.filter(hub__in=hubs).select_related("hub", "product")
            context["recent_stock"] = balances.order_by("quantity", "product__name")[:8]
            context["stock_columns"] = (
                {"label": "Hub", "field": "hub__name"},
                {"label": "Product", "field": "product__name"},
                {"label": "On hand", "field": "quantity"},
                {"label": "Reorder level", "field": "product__reorder_level"},
            )

        if user.role in (Role.SUPER_ADMIN, Role.ADMIN):
            pending_commissions = SalesAgentCommission.objects.filter(
                status=SalesAgentCommission.Status.PENDING,
                sale__hub__in=hubs,
            )
            context["dashboard_stats"] = [
                ("Active hubs", hubs.filter(status=Hub.Status.ACTIVE).count()),
                ("Products", Product.objects.filter(is_active=True).count()),
                ("Completed sales", sales.count()),
                ("Sales value", sales.aggregate(total=Sum("total"))["total"] or 0),
                ("Pending commissions", pending_commissions.count()),
            ]
        elif user.role == Role.SALES_AGENT:
            agent_sales = self.apply_date_range(
                Sale.objects.filter(agent=user, status=Sale.Status.COMPLETED),
                "completed_at",
            )
            agent_pending_commissions = SalesAgentCommission.objects.filter(
                agent=user,
                status=SalesAgentCommission.Status.PENDING,
                sale__hub__in=hubs,
            )
            context["dashboard_stats"] = [
                ("Completed sales", agent_sales.count()),
                ("Sales total", agent_sales.aggregate(total=Sum("total"))["total"] or 0),
                ("Pending commission", agent_pending_commissions.aggregate(total=Sum("amount"))["total"] or 0),
            ]
            context["recent_commissions"] = SalesAgentCommission.objects.filter(
                agent=user
            )
            if active_hub:
                context["recent_commissions"] = context["recent_commissions"].filter(
                    sale__hub=active_hub
                )
            elif hub_error:
                context["recent_commissions"] = context["recent_commissions"].none()
            context["recent_commissions"] = self.apply_date_range(
                context["recent_commissions"], "created_at"
            ).select_related("sale").order_by("-created_at")[:8]
        elif user.role == Role.WORKER:
            all_salaries = SalaryRecord.objects.filter(worker__user=user)
            all_salaries = all_salaries.filter(worker__hub__in=hubs)
            salaries = self.apply_date_range(all_salaries, "period_start")
            context["dashboard_stats"] = [
                ("Salary records", salaries.count()),
                (
                    "Awaiting payment (current)",
                    all_salaries.filter(status=SalaryRecord.Status.APPROVED).count(),
                ),
            ]
            context["recent_salaries"] = salaries.select_related("worker").order_by("-period_start")[:8]
        elif user.role == Role.BENEFICIARY:
            from apps.beneficiaries.models import Business

            businesses = Business.objects.filter(beneficiary__user=user)
            if active_hub:
                businesses = businesses.filter(hub=active_hub)
            elif hub_error:
                businesses = businesses.none()
            context["dashboard_stats"] = [
                ("Businesses", businesses.count()),
                ("Active businesses", businesses.filter(status=Business.Status.ACTIVE).count()),
                ("Completed sales", sales.count()),
                ("Sales value", sales.aggregate(total=Sum("total"))["total"] or 0),
            ]
            context["recent_businesses"] = businesses.select_related("hub").order_by("name")[:8]
        else:
            context["dashboard_stats"] = [
                ("Your hubs", hubs.count()),
                ("Completed sales", sales.count()),
                ("Sales value", sales.aggregate(total=Sum("total"))["total"] or 0),
            ]

        if user.role in (Role.SUPER_ADMIN, Role.ADMIN, Role.HUB_MANAGER, Role.FINANCE_OFFICER):
            commissions = SalesAgentCommission.objects.filter(
                status=SalesAgentCommission.Status.PENDING
            )
            salaries = SalaryRecord.objects.filter(status=SalaryRecord.Status.PENDING)
            commissions = commissions.filter(sale__hub__in=hubs)
            salaries = salaries.filter(worker__hub__in=hubs)
            context["pending_commissions"] = commissions.select_related(
                "agent", "sale", "sale__hub"
            ).order_by("-created_at")[:8]
            context["pending_salaries"] = salaries.select_related(
                "worker", "worker__user", "worker__hub"
            ).order_by("-created_at")[:8]
            context["pending_commission_count"] = commissions.count()
            context["pending_salary_count"] = salaries.count()
            if is_platform_admin or user.role == Role.HUB_MANAGER:
                context["low_stock_count"] = InventoryBalance.objects.filter(
                    hub__in=hubs,
                    hub__status=Hub.Status.ACTIVE,
                    product__is_active=True,
                    product__reorder_level__gt=0,
                    quantity__lte=F("product__reorder_level"),
                ).count()
                context["dashboard_stats"].append(("Low stock items", context["low_stock_count"]))
        context.update(
            available_hubs=available_hubs,
            active_hub=active_hub,
            active_hub_id=active_hub.pk if active_hub else "",
            hub_error=hub_error,
        )
        return context


class SettingsHomeView(LoginRequiredMixin, UserPassesTestMixin, PageMixin, TemplateView):
    template_name = "settings/settings_home.html"
    page_title = "Settings"

    def test_func(self):
        return self.request.user.role in (Role.SUPER_ADMIN, Role.ADMIN)


def permission_denied(request, exception=None):
    return render(request, "errors/403.html", status=403)


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)


def server_error(request):
    return render(request, "errors/500.html", status=500)