from datetime import date, datetime, time, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.conf import settings
from django.core.cache import cache
from django.db import connection, models
from django.db.models import F, Sum
from django.http import JsonResponse
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
        default_end = today
        default_start = today - timedelta(days=29)
        month_start = default_start
        month_end = default_end
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
            start_date, end_date = default_start, default_end
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
        from apps.members.models import MemberProfile, Business
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

        total_members = MemberProfile.objects.count() if is_platform_admin else MemberProfile.objects.filter(hub__in=hubs).count()
        total_contribution_amount = (
            Business.objects.aggregate(total=Sum("amount"))["total"] or 0
            if is_platform_admin
            else Business.objects.filter(hub__in=hubs).aggregate(total=Sum("amount"))["total"] or 0
        )

        if is_platform_admin:
            context["dashboard_intro"] = (
                "A live overview of total members, contributions (some eligible for commissions), completed sales and commission activity."
            )
        elif user.role in (Role.HUB_MANAGER, Role.FINANCE_OFFICER, Role.VIEWER):
            sales = sales.filter(hub__in=hubs)
        elif user.role == Role.SALES_AGENT:
            sales = sales.filter(agent=user)
        elif user.role == Role.MEMBER:
            sales = sales.filter(business__member__user=user)
        else:
            sales = sales.none()
        if active_hub:
            sales = sales.filter(hub=active_hub)
        elif hub_error:
            sales = sales.none()
        sales = self.apply_date_range(sales, "completed_at")

        if not is_platform_admin:
            context["dashboard_intro"] = {
                Role.HUB_MANAGER: "Recent sales, stock levels, member contributions, and approvals for your hubs (some members receive commissions).",
                Role.FINANCE_OFFICER: "Recent sales and outstanding payment approvals for your hubs.",
                Role.SALES_AGENT: "Your completed sales and commission activity.",
                Role.WORKER: "Your salary records and payment history.",
                Role.MEMBER: "Your contributions and associated sales activity.",
                Role.VIEWER: "A read-only summary of activity at your hubs.",
            }.get(user.role, "Your latest Agile Hub activity.")

        show_hub_column = is_platform_admin and not active_hub

        context["recent_sales"] = sales.select_related("hub", "agent", "member").order_by("-completed_at")[:8]
        sales_cols = [{"label": "Date", "field": "completed_at"}]
        if show_hub_column:
            sales_cols.append({"label": "Hub", "field": "hub__name"})
        sales_cols.extend([
            {"label": "Agent / Member", "field": "seller_display"},
            {"label": "Customer", "field": "customer_display"},
            {"label": "Total", "field": "total"},
            {"label": "Status", "field": "status"},
        ])
        context["sales_columns"] = tuple(sales_cols)

        if is_platform_admin or user.role in (Role.HUB_MANAGER, Role.FINANCE_OFFICER, Role.VIEWER):
            balances = InventoryBalance.objects.filter(hub__in=hubs).select_related("hub", "product")
            context["recent_stock"] = balances.order_by("quantity", "product__name")[:8]
            stock_cols = []
            if show_hub_column:
                stock_cols.append({"label": "Hub", "field": "hub__name"})
            stock_cols.extend([
                {"label": "Product", "field": "product__name"},
                {"label": "On hand", "field": "quantity"},
                {"label": "Reorder level", "field": "product__reorder_level"},
            ])
            context["stock_columns"] = tuple(stock_cols)

        commissions_earned_qs = SalesAgentCommission.objects.filter(
            status__in=[SalesAgentCommission.Status.APPROVED, SalesAgentCommission.Status.PAID]
        )
        if not is_platform_admin:
            commissions_earned_qs = commissions_earned_qs.filter(sale__hub__in=hubs)
        if active_hub:
            commissions_earned_qs = commissions_earned_qs.filter(sale__hub=active_hub)
        elif hub_error:
            commissions_earned_qs = commissions_earned_qs.none()

        start_at = timezone.make_aware(datetime.combine(start_date, time.min))
        end_at = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
        commissions_earned_qs = commissions_earned_qs.filter(
            sale__completed_at__gte=start_at,
            sale__completed_at__lt=end_at,
        )
        agent_commission_earned_amount = commissions_earned_qs.filter(sale__agent__isnull=False).aggregate(total=Sum("amount"))["total"] or 0
        member_commission_earned_amount = commissions_earned_qs.filter(sale__member__isnull=False).aggregate(total=Sum("amount"))["total"] or 0

        from apps.commissions.models import ServiceCommission
        service_commissions_earned_qs = ServiceCommission.objects.filter(
            status__in=[ServiceCommission.Status.APPROVED, ServiceCommission.Status.PAID]
        )
        if not is_platform_admin:
            service_commissions_earned_qs = service_commissions_earned_qs.filter(booking__hub__in=hubs)
        if active_hub:
            service_commissions_earned_qs = service_commissions_earned_qs.filter(booking__hub=active_hub)
        elif hub_error:
            service_commissions_earned_qs = service_commissions_earned_qs.none()

        service_commissions_earned_qs = service_commissions_earned_qs.filter(
            booking__start_date__gte=start_at,
            booking__start_date__lt=end_at,
        )
        service_commission_earned_amount = service_commissions_earned_qs.aggregate(total=Sum("amount"))["total"] or 0

        total_sales_value = sales.aggregate(total=Sum("total"))["total"] or 0

        from django.db.models.functions import TruncDate
        daily_sales = (
            sales.annotate(day=TruncDate("completed_at"))
            .values("day")
            .annotate(total=Sum("total"))
            .order_by("day")
        )
        raw_chart_data = [
            {"label": item["day"].strftime("%b %d") if item["day"] else "Unknown", "value": float(item["total"] or 0)}
            for item in daily_sales if item["day"]
        ]
        max_val = max([item["value"] for item in raw_chart_data], default=1)
        if max_val == 0:
            max_val = 1
        chart_data = [
            {
                "label": item["label"],
                "value": item["value"],
                "pct": max(10, int((item["value"] / max_val) * 100))
            }
            for item in raw_chart_data
        ]
        context["chart_data"] = chart_data
        context["chart_title"] = "Daily Sales Overview"

        context["dashboard_stats"] = [
            ("Total membership", total_members),
            ("Total Membership Contribution", total_contribution_amount),
            ("Total Sales value", total_sales_value),
            ("Commission Earned by Sales Agents", agent_commission_earned_amount),
            ("Commission Earned by Members (Sales Agents)", member_commission_earned_amount),
            ("Commission Earned by Service Providers", service_commission_earned_amount),
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
        context.update(
            available_hubs=available_hubs,
            active_hub=active_hub,
            active_hub_id=active_hub.pk if active_hub else "",
            hub_error=hub_error,
            show_hub_column=show_hub_column,
        )
        return context


class SettingsHomeView(LoginRequiredMixin, UserPassesTestMixin, PageMixin, TemplateView):
    template_name = "settings/settings_home.html"
    page_title = "Settings"

    def test_func(self):
        return self.request.user.role in (Role.SUPER_ADMIN, Role.ADMIN, Role.HUB_MANAGER)


def permission_denied(request, exception=None):
    return render(request, "errors/403.html", status=403)


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)


def server_error(request):
    return render(request, "errors/500.html", status=500)


def health_check(request):
    """Liveness and readiness health probe for container orchestrators and load balancers."""
    data = {"status": "ok", "timestamp": timezone.now().isoformat()}
    status_code = 200

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        data["database"] = "ok"
    except Exception as exc:
        data["database"] = f"unhealthy: {exc}"
        data["status"] = "unhealthy"
        status_code = 503

    try:
        cache.set("_health_probe", "1", 10)
        cached = cache.get("_health_probe")
        data["cache"] = "ok" if cached == "1" else "degraded"
    except Exception as exc:
        data["cache"] = f"degraded: {exc}"

    return JsonResponse(data, status=status_code)
