from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from apps.core.generic import ProtectedCreateView, ProtectedUpdateView, ScopedModelListView
from apps.core.exports import ScopedModelExportView
from apps.core.mixins import PageMixin
from apps.hubs.permissions import selected_hub

from .forms import (
    BookingActionForm,
    HubResourceForm,
    ServiceBookingForm,
    ServiceTypeForm,
    ServiceProviderForm,
    ServiceProviderActionForm,
)
from .models import HubResource, ServiceBooking, ServiceType, ServiceProvider, ProviderType
from .services import (
    cancel_service_booking,
    complete_service_booking,
    record_booking_payment,
    start_service_booking,
    register_service_provider,
    suspend_service_provider,
    reactivate_service_provider,
)


# ---------------------------------------------------------------------------
# Service Bookings (Ripening batches, Harvester/Machinery rentals)
# ---------------------------------------------------------------------------
class ServiceBookingListView(ScopedModelListView):
    model = ServiceBooking
    page_title = "Service Bookings"
    template_name = "services/booking_list.html"
    export_url_name = "services:booking_export"
    row_detail_url_name = "services:booking_detail"
    columns = (
        {"label": "Service", "field": "service_type__name"},
        {"label": "Equipment / Chamber", "field": "resource__name"},
        {"label": "Customer / Client", "field": "client_display"},
        {"label": "Start Date", "field": "start_date"},
        {"label": "End Date", "field": "end_date"},
        {"label": "Total Amount", "field": "total_amount"},
        {"label": "Status", "field": "status"},
        {"label": "Payment", "field": "payment_status"},
    )
    search_fields = (
        "customer_name",
        "customer_phone",
        "service_type__name",
        "resource__name",
        "member__user__first_name",
        "member__user__last_name",
    )
    create_url_name = "services:booking_create"
    create_permission = "services.add_servicebooking"
    row_edit_url_name = "services:booking_edit"
    row_edit_permission = "services.change_servicebooking"
    filter_hub = True
    hub_filter_paths = ("hub",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = self.get_queryset()
        context["total_bookings_count"] = base_qs.count()
        context["active_bookings_count"] = base_qs.filter(status=ServiceBooking.Status.IN_PROGRESS).count()
        context["completed_bookings_count"] = base_qs.filter(status=ServiceBooking.Status.COMPLETED).count()
        context["total_bookings_revenue"] = base_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
        return context


class ServiceBookingCreateView(ProtectedCreateView):
    model = ServiceBooking
    form_class = ServiceBookingForm
    page_title = "New Service Booking"
    success_url_name = "services:booking_list"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class ServiceBookingUpdateView(ProtectedUpdateView):
    model = ServiceBooking
    form_class = ServiceBookingForm
    page_title = "Edit Service Booking"
    success_url_name = "services:booking_list"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class ServiceBookingDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = ServiceBooking
    template_name = "services/booking_detail.html"
    permission_required = "services.view_servicebooking"
    page_title = "Service Booking Details"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action_form"] = BookingActionForm()
        context["booking_commissions"] = self.object.commissions.select_related("service_type").all()
        return context


class ServiceBookingActionView(LoginRequiredMixin, View):
    """Handles lifecycle actions: start, complete, cancel, record payment."""

    def post(self, request, pk):
        booking = get_object_or_404(ServiceBooking, pk=pk)
        action = request.POST.get("action")
        form = BookingActionForm(request.POST)

        notes = ""
        payment_reference = ""
        if form.is_valid():
            notes = form.cleaned_data.get("notes", "")
            payment_reference = form.cleaned_data.get("payment_reference", "")

        try:
            if action == "start":
                start_service_booking(booking_id=booking.pk, actor=request.user)
                messages.success(request, f"Booking '{booking}' is now In Progress.")
            elif action == "complete":
                actual_qty = None
                if request.POST.get("actual_quantity"):
                    actual_qty = Decimal(request.POST.get("actual_quantity"))
                complete_service_booking(
                    booking_id=booking.pk, actor=request.user, actual_quantity=actual_qty, notes=notes
                )
                messages.success(request, f"Booking '{booking}' has been marked as Completed.")
            elif action == "cancel":
                cancel_service_booking(booking_id=booking.pk, actor=request.user, reason=notes)
                messages.warning(request, f"Booking '{booking}' has been cancelled.")
            elif action == "pay":
                record_booking_payment(
                    booking_id=booking.pk, payment_reference=payment_reference, actor=request.user
                )
                messages.success(request, f"Payment recorded for '{booking}'.")
            else:
                messages.error(request, f"Unknown action '{action}'.")
        except ValidationError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"Action failed: {exc}")

        return redirect("services:booking_detail", pk=booking.pk)


# ---------------------------------------------------------------------------
# Hub Resources (Ripening Chambers, Combine Harvesters, Tractors)
# ---------------------------------------------------------------------------
class HubResourceListView(ScopedModelListView):
    model = HubResource
    page_title = "Hub Equipment & Facilities"
    template_name = "services/resource_list.html"
    export_url_name = "services:resource_export"
    columns = (
        {"label": "Code", "field": "code"},
        {"label": "Name", "field": "name"},
        {"label": "Service Type", "field": "service_type__name"},
        {"label": "Capacity", "field": "capacity"},
        {"label": "Capacity Unit", "field": "capacity_unit"},
        {"label": "Status", "field": "status"},
        {"label": "Operator", "field": "operator_name"},
    )
    search_fields = ("code", "name", "operator_name", "service_type__name")
    create_url_name = "services:resource_create"
    create_permission = "services.add_hubresource"
    row_edit_url_name = "services:resource_edit"
    row_edit_permission = "services.change_hubresource"
    filter_hub = True
    hub_filter_paths = ("hub",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = self.get_queryset()
        context["total_resources_count"] = base_qs.count()
        context["available_resources_count"] = base_qs.filter(status=HubResource.Status.AVAILABLE).count()
        context["in_use_resources_count"] = base_qs.filter(status=HubResource.Status.IN_USE).count()
        context["maintenance_resources_count"] = base_qs.filter(status=HubResource.Status.MAINTENANCE).count()
        return context


class HubResourceCreateView(ProtectedCreateView):
    model = HubResource
    form_class = HubResourceForm
    page_title = "Add Equipment / Facility"
    success_url_name = "services:resource_list"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class HubResourceUpdateView(ProtectedUpdateView):
    model = HubResource
    form_class = HubResourceForm
    page_title = "Edit Equipment / Facility"
    success_url_name = "services:resource_list"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class HubResourceDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = HubResource
    template_name = "services/resource_detail.html"
    permission_required = "services.view_hubresource"
    page_title = "Equipment Details"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_bookings"] = self.object.bookings.order_by("-start_date")[:10]
        return context


# ---------------------------------------------------------------------------
# Service Types (Catalog)
# ---------------------------------------------------------------------------
class ServiceTypeListView(ScopedModelListView):
    model = ServiceType
    page_title = "Service Catalog"
    template_name = "services/service_type_list.html"
    export_url_name = "services:service_type_export"
    columns = (
        {"label": "Code", "field": "code"},
        {"label": "Name", "field": "name"},
        {"label": "Category", "field": "category"},
        {"label": "Pricing Unit", "field": "pricing_unit"},
        {"label": "Standard Rate", "field": "standard_rate"},
        {"label": "Active", "field": "is_active"},
    )
    search_fields = ("code", "name", "category")
    create_url_name = "services:service_type_create"
    create_permission = "services.add_servicetype"
    row_edit_url_name = "services:service_type_edit"
    row_edit_permission = "services.change_servicetype"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = self.get_queryset()
        context["total_services_count"] = base_qs.count()
        context["active_services_count"] = base_qs.filter(is_active=True).count()
        return context


class ServiceTypeCreateView(ProtectedCreateView):
    model = ServiceType
    form_class = ServiceTypeForm
    page_title = "Add Service to Catalog"
    success_url_name = "services:service_type_list"


class ServiceTypeUpdateView(ProtectedUpdateView):
    model = ServiceType
    form_class = ServiceTypeForm
    page_title = "Edit Service"
    success_url_name = "services:service_type_list"


class ServiceTypeDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = ServiceType
    template_name = "services/service_type_detail.html"
    permission_required = "services.view_servicetype"
    page_title = "Service Details"


# ---------------------------------------------------------------------------
# Service Providers (Internal & External)
# ---------------------------------------------------------------------------
class ServiceProviderListView(ScopedModelListView):
    model = ServiceProvider
    page_title = "Service Providers"
    template_name = "services/provider_list.html"
    export_url_name = "services:provider_export"
    row_detail_url_name = "services:provider_detail"
    columns = (
        {"label": "Name", "field": "name"},
        {"label": "Provider Type", "field": "provider_type_display"},
        {"label": "Service Category", "field": "service_category_display"},
        {"label": "Phone", "field": "phone_number"},
        {"label": "Status", "field": "status_display"},
        {"label": "Payment Status", "field": "payment_status_display"},
    )
    search_fields = ("name", "phone_number", "email", "member__user__first_name", "member__user__last_name", "member__name")
    create_url_name = "services:provider_create"
    create_label = "Register provider"
    create_permission = "services.add_serviceprovider"
    row_edit_url_name = "services:provider_edit"
    row_edit_permission = "services.change_serviceprovider"
    filter_fields = (
        ("provider_type", ServiceProvider.provider_type.field.choices if hasattr(ServiceProvider.provider_type.field, 'choices') else ()),
        ("status", ServiceProvider.status.field.choices if hasattr(ServiceProvider.status.field, 'choices') else ()),
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.GET.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.members.views import _provider_stats
        context.update(_provider_stats())
        context["active_provider_tab"] = context.get("active_provider_tab", "all")
        return context


class InternalServiceProviderListView(ServiceProviderListView):
    page_title = "Internal Service Providers (Members)"

    def get_queryset(self):
        return super().get_queryset().filter(provider_type=ProviderType.INTERNAL)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_provider_tab"] = "internal"
        return context


class ExternalServiceProviderListView(ServiceProviderListView):
    page_title = "External Service Providers (Non-Members)"

    def get_queryset(self):
        return super().get_queryset().filter(provider_type=ProviderType.EXTERNAL)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_provider_tab"] = "external"
        return context


class ServiceProviderCreateView(ProtectedCreateView):
    model = ServiceProvider
    form_class = ServiceProviderForm
    template_name = "services/serviceprovider_form.html"
    page_title = "Register Service Provider"
    success_url_name = "services:provider_list"
    cancel_url_name = "services:provider_list"


class ServiceProviderUpdateView(ProtectedUpdateView):
    model = ServiceProvider
    form_class = ServiceProviderForm
    template_name = "services/serviceprovider_form.html"
    page_title = "Edit Service Provider"
    success_url_name = "services:provider_list"
    cancel_url_name = "services:provider_list"


class ServiceProviderDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = ServiceProvider
    template_name = "services/provider_detail.html"
    context_object_name = "provider"
    permission_required = "services.view_serviceprovider"
    page_title = "Service Provider Details"

    def get_breadcrumbs(self):
        return [
            ("Service Providers", reverse("services:provider_list")),
            (self.object.name, None),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action_form"] = ServiceProviderActionForm()
        bookings = self.object.bookings.select_related("service_type", "resource", "hub").order_by("-start_date")
        commissions = self.object.commissions.select_related("booking", "service_type").order_by("-created_at")

        sales_commissions = []
        sales_records = []
        user = self.object.member.user if (self.object.member and self.object.member.user) else None
        if user:
            from apps.commissions.models import SalesAgentCommission
            from apps.sales.models import Sale
            sales_commissions = SalesAgentCommission.objects.filter(agent=user).select_related("sale__hub").order_by("-created_at")
            sales_records = Sale.objects.filter(agent=user).select_related("hub").order_by("-completed_at")[:20]

        total_commissions = commissions.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        total_sales_commissions = sum((c.amount for c in sales_commissions), Decimal("0.00"))
        paid_commissions = commissions.filter(status="PAID").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        pending_commissions = commissions.filter(status__in=["PENDING", "APPROVED"]).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        context.update(
            bookings=bookings[:20],
            commissions=commissions[:20],
            sales_commissions=sales_commissions[:20],
            sales_records=sales_records,
            total_bookings_count=bookings.count(),
            total_commissions=total_commissions,
            total_sales_commissions=total_sales_commissions,
            paid_commissions=paid_commissions,
            pending_commissions=pending_commissions,
            can_edit_provider=self.request.user.has_perm("services.change_serviceprovider"),
            can_manage_status=self.request.user.has_perm("services.change_serviceprovider") or self.request.user.has_perm("services.suspend_serviceprovider"),
        )
        return context


class ServiceProviderActionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        provider = get_object_or_404(ServiceProvider, pk=pk)
        action = request.POST.get("action")
        form = ServiceProviderActionForm(request.POST)
        reason = form.cleaned_data.get("reason", "") if form.is_valid() else ""

        try:
            if action == "suspend":
                suspend_service_provider(provider_id=provider.pk, reason=reason, actor=request.user)
                messages.warning(request, f"Service provider '{provider}' has been suspended.")
            elif action == "reactivate":
                reactivate_service_provider(provider_id=provider.pk, actor=request.user)
                messages.success(request, f"Service provider '{provider}' has been reactivated.")
            else:
                messages.error(request, f"Unknown action '{action}'.")
        except ValidationError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"Action failed: {exc}")

        return redirect("services:provider_detail", pk=provider.pk)


class BookingExportView(ScopedModelExportView):
    list_view_class = ServiceBookingListView


class ResourceExportView(ScopedModelExportView):
    list_view_class = HubResourceListView


class ServiceTypeExportView(ScopedModelExportView):
    list_view_class = ServiceTypeListView


class ProviderExportView(ScopedModelExportView):
    list_view_class = ServiceProviderListView
