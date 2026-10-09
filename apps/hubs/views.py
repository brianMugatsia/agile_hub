from datetime import date, datetime, time, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import DetailView, TemplateView

from apps.core.mixins import PageMixin
from .forms import HubForm
from .models import Hub
from apps.core.generic import ProtectedCreateView, ProtectedUpdateView, ScopedModelListView, hubs_for_user
from apps.core.scoping import scope_queryset
from apps.sales.models import Sale


class HubListView(ScopedModelListView):
    model = Hub
    page_title = "Hubs"
    columns = (
        {"label": "Code", "field": "code"},
        {"label": "Hub", "field": "name"},
        {"label": "Region", "field": "region"},
        {"label": "Manager", "field": "manager__display_name"},
        {"label": "Status", "field": "status"},
    )
    search_fields = ("code", "name", "region")
    create_url_name = "hubs:create"
    create_permission = "hubs.add_hub"
    row_edit_url_name = "hubs:edit"
    row_edit_permission = "hubs.change_hub"


class HubCreateView(ProtectedCreateView):
    model = Hub
    form_class = HubForm
    page_title = "Create hub"
    success_url_name = "hubs:list"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.role not in ("SUPER_ADMIN", "ADMIN"):
            form.fields["manager"].queryset = form.fields["manager"].queryset.filter(
                hub_memberships__hub__in=hubs_for_user(self.request.user)
            ).distinct()
        return form


class HubUpdateView(ProtectedUpdateView):
    model = Hub
    form_class = HubForm
    page_title = "Edit hub"
    success_url_name = "hubs:list"
    cancel_url_name = "hubs:list"

    def get_queryset(self):
        return scope_queryset(Hub.objects.all(), self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.role not in ("SUPER_ADMIN", "ADMIN"):
            manager_field = form.fields["manager"]
            manager_field.queryset = manager_field.queryset.filter(
                hub_memberships__hub__in=hubs_for_user(self.request.user)
            )
            if self.object.manager_id:
                manager_field.queryset |= manager_field.queryset.model.objects.filter(
                    pk=self.object.manager_id
                )
            manager_field.queryset = manager_field.queryset.distinct()
        return form


class HubDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = Hub
    template_name = "hubs/hub_detail.html"
    context_object_name = "hub"
    permission_required = "hubs.view_hub"
    page_title = "Hub details"

    def get_queryset(self):
        return scope_queryset(Hub.objects.select_related("manager"), self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_edit_hub"] = self.request.user.has_perm("hubs.change_hub")
        return context


class HubPerformanceView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, TemplateView):
    template_name = "hubs/hub_performance.html"
    permission_required = "hubs.view_hub"
    page_title = "Hub performance"
    max_date_range_days = 366

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
        if start and end and (end - start).days + 1 > self.max_date_range_days:
            return HttpResponseBadRequest("Choose a date range of no more than 366 days.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hub = get_object_or_404(
            scope_queryset(Hub.objects.all(), self.request.user),
            pk=self.kwargs["pk"],
        )
        today = timezone.localdate()
        start_value = self.request.GET.get("start", "")
        end_value = self.request.GET.get("end", "")
        start = parse_date(start_value) if start_value else None
        end = parse_date(end_value) if end_value else None
        if start and not end:
            period_start = period_end = start
        elif end and not start:
            period_start = period_end = end
        else:
            period_start = start or today.replace(day=1)
            period_end = end or today

        start_at = timezone.make_aware(datetime.combine(period_start, time.min))
        end_at = timezone.make_aware(
            datetime.combine(period_end + timedelta(days=1), time.min)
        )
        sales = Sale.objects.filter(
            hub=hub,
            status=Sale.Status.COMPLETED,
            completed_at__gte=start_at,
            completed_at__lt=end_at,
        )
        context.update(
            page_title=f"{hub.name} performance",
            hub=hub,
            period_start=period_start,
            period_end=period_end,
            sales_count=sales.count(),
            sales_total=sales.aggregate(total=Sum("total"))["total"] or 0,
            active_agents=sales.values("agent_id").distinct().count(),
            object_list=sales.select_related("agent").order_by("-completed_at")[:25],
            columns=(
                {"label": "Completed", "field": "completed_at"},
                {"label": "Agent", "field": "agent__display_name"},
                {"label": "Customer", "field": "customer_name"},
                {"label": "Revenue", "field": "total"},
            ),
        )
        return context