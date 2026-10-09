from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import DetailView, TemplateView

from apps.core.mixins import PageMixin
from apps.inventory.models import InventoryBalance
from .forms import HubForm
from .models import Hub
from apps.core.generic import ProtectedCreateView, ProtectedUpdateView, ScopedModelListView, hubs_for_user
from apps.core.scoping import scope_queryset
from apps.sales.models import Sale

MONEY = DecimalField(max_digits=14, decimal_places=2)


def _month_start_at():
    month_start = timezone.localdate().replace(day=1)
    return timezone.make_aware(datetime.combine(month_start, time.min))


class HubListView(ScopedModelListView):
    model = Hub
    template_name = "hubs/hub_list.html"
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
    create_label = "Add hub"
    create_permission = "hubs.add_hub"
    row_edit_url_name = "hubs:edit"
    row_edit_permission = "hubs.change_hub"

    def get_queryset(self):
        queryset = super().get_queryset()
        revenue = (
            Sale.objects.filter(
                hub=OuterRef("pk"),
                status=Sale.Status.COMPLETED,
                completed_at__gte=_month_start_at(),
            )
            .order_by()
            .values("hub")
            .annotate(total=Sum("total"))
            .values("total")
        )
        return queryset.annotate(
            n_staff=Count("workers", filter=Q(workers__is_active=True), distinct=True),
            n_businesses=Count("businesses", distinct=True),
            n_beneficiaries=Count("beneficiaries", distinct=True),
            n_low_stock=Count(
                "stock_balances",
                filter=Q(
                    stock_balances__product__is_active=True,
                    stock_balances__product__reorder_level__gt=0,
                    stock_balances__quantity__lte=F("stock_balances__product__reorder_level"),
                ),
                distinct=True,
            ),
            month_revenue=Coalesce(
                Subquery(revenue, output_field=MONEY),
                Value(Decimal("0.00")),
                output_field=MONEY,
            ),
        )


class HubCreateView(ProtectedCreateView):
    model = Hub
    form_class = HubForm
    template_name = "hubs/hub_form.html"
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
    template_name = "hubs/hub_form.html"
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
        hub = self.object
        month_sales = Sale.objects.filter(
            hub=hub,
            status=Sale.Status.COMPLETED,
            completed_at__gte=_month_start_at(),
        )
        low_stock = InventoryBalance.objects.filter(
            hub=hub,
            product__is_active=True,
            product__reorder_level__gt=0,
            quantity__lte=F("product__reorder_level"),
        ).count()
        context.update(
            can_edit_hub=self.request.user.has_perm("hubs.change_hub"),
            staff_count=hub.workers.filter(is_active=True).count(),
            business_count=hub.businesses.count(),
            beneficiary_count=hub.beneficiaries.count(),
            low_stock_count=low_stock,
            month_sales_count=month_sales.count(),
            month_revenue=month_sales.aggregate(total=Sum("total"))["total"] or Decimal("0.00"),
        )
        return context


def _preset_links(today, period_start, period_end):
    first_this_month = today.replace(day=1)
    last_previous_month = first_this_month - timedelta(days=1)
    presets = (
        ("This month", first_this_month, today),
        ("Last 7 days", today - timedelta(days=6), today),
        ("Last 30 days", today - timedelta(days=29), today),
        ("Last month", last_previous_month.replace(day=1), last_previous_month),
        ("Year to date", date(today.year, 1, 1), today),
    )
    return [
        {
            "label": label,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "active": (start, end) == (period_start, period_end),
        }
        for label, start, end in presets
    ]


def _revenue_bars(sales, period_start, period_end):
    """Daily revenue bars, or monthly bars when the period is longer than about three months."""
    span_days = (period_end - period_start).days + 1
    monthly = span_days > 92
    bucket = TruncMonth("completed_at") if monthly else TruncDate("completed_at")
    rows = (
        sales.annotate(bucket=bucket)
        .values("bucket")
        .annotate(total=Sum("total"))
        .order_by("bucket")
    )
    totals = {}
    for row in rows:
        key = timezone.localtime(row["bucket"]).date() if monthly else row["bucket"]
        totals[key] = row["total"] or Decimal("0.00")
    if not totals:
        return [], "day", Decimal("0.00"), "", ""

    buckets = []
    if monthly:
        cursor = period_start.replace(day=1)
        while cursor <= period_end:
            buckets.append(cursor)
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        buckets = [period_start + timedelta(days=i) for i in range(span_days)]

    peak = max(totals.values())
    bars = []
    for item in buckets:
        total = totals.get(item, Decimal("0.00"))
        label = f"{item:%b %Y}" if monthly else f"{item.day} {item:%b}"
        pct = float(total / peak * 100) if peak else 0.0
        bars.append({"label": label, "total": total, "pct": pct})
    return bars, ("month" if monthly else "day"), peak, bars[0]["label"], bars[-1]["label"]


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
        bars, bars_unit, bars_peak, bars_first, bars_last = _revenue_bars(
            sales, period_start, period_end
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
            presets=_preset_links(today, period_start, period_end),
            bars=bars,
            bars_unit=bars_unit,
            bars_peak=bars_peak,
            bars_first=bars_first,
            bars_last=bars_last,
            columns=(
                {"label": "Completed", "field": "completed_at"},
                {"label": "Agent", "field": "agent__display_name"},
                {"label": "Customer", "field": "customer_name"},
                {"label": "Revenue", "field": "total"},
            ),
        )
        return context