from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.conf import settings
from django.db.models import F, Sum
from django.shortcuts import render
from django.views.generic import TemplateView

from apps.accounts.roles import Role
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

    def get_template_names(self):
        return [f"dashboard/{self.request.user.role.lower()}.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        from apps.commissions.models import SalesAgentCommission
        from apps.hubs.models import Hub
        from apps.inventory.models import InventoryBalance
        from apps.payroll.models import SalaryRecord
        from apps.products.models import Product
        from apps.sales.models import Sale
        from apps.core.generic import hubs_for_user

        is_platform_admin = user.role in (Role.SUPER_ADMIN, Role.ADMIN)
        hubs = Hub.objects.all() if is_platform_admin else hubs_for_user(user)
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
            completed_sales = Sale.objects.filter(status=Sale.Status.COMPLETED)
            context["dashboard_stats"] = [
                ("Active hubs", Hub.objects.filter(status=Hub.Status.ACTIVE).count()),
                ("Products", Product.objects.filter(is_active=True).count()),
                ("Completed sales", completed_sales.count()),
                ("Sales value", completed_sales.aggregate(total=Sum("total"))["total"] or 0),
                (
                    "Pending commissions",
                    SalesAgentCommission.objects.filter(status=SalesAgentCommission.Status.PENDING).count(),
                ),
            ]
            context["low_stock_count"] = InventoryBalance.objects.filter(
                quantity__lte=F("product__reorder_level")
            ).count()
        elif user.role == Role.SALES_AGENT:
            agent_sales = Sale.objects.filter(agent=user, status=Sale.Status.COMPLETED)
            context["dashboard_stats"] = [
                ("Completed sales", agent_sales.count()),
                ("Sales total", agent_sales.aggregate(total=Sum("total"))["total"] or 0),
                (
                    "Pending commission",
                    SalesAgentCommission.objects.filter(
                        agent=user, status=SalesAgentCommission.Status.PENDING
                    ).aggregate(total=Sum("amount"))["total"] or 0,
                ),
            ]
            context["recent_commissions"] = SalesAgentCommission.objects.filter(
                agent=user
            ).select_related("sale").order_by("-created_at")[:8]
        elif user.role == Role.WORKER:
            salaries = SalaryRecord.objects.filter(worker__user=user)
            context["dashboard_stats"] = [
                ("Salary records", salaries.count()),
                ("Awaiting payment", salaries.filter(status=SalaryRecord.Status.APPROVED).count()),
            ]
            context["recent_salaries"] = salaries.select_related("worker").order_by("-period_start")[:8]
        elif user.role == Role.BENEFICIARY:
            from apps.beneficiaries.models import Business

            businesses = Business.objects.filter(beneficiary__user=user)
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
            if not is_platform_admin:
                commissions = commissions.filter(sale__hub__in=hubs)
                salaries = salaries.filter(worker__hub__in=hubs)
            context["pending_commissions"] = commissions.select_related(
                "agent", "sale", "sale__hub"
            ).order_by("-created_at")[:8]
            context["pending_salaries"] = salaries.select_related(
                "worker", "worker__user", "worker__hub"
            ).order_by("-created_at")[:8]
            if is_platform_admin:
                context["dashboard_stats"].append(("Low stock items", context["low_stock_count"]))
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