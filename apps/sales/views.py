from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.urls import reverse
from django.views.generic import DetailView, FormView

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.beneficiaries.models import Business
from apps.core.generic import ProtectedUpdateView, ScopedModelListView, hubs_for_user
from apps.core.exports import ScopedModelExportView
from apps.core.mixins import PageMixin
from apps.core.scoping import scope_queryset
from apps.hubs.models import HubMembership
from apps.sales.services import complete_sale

from .forms import SaleEntryForm, SaleUpdateForm
from .models import Sale


class SaleListView(ScopedModelListView):
    model = Sale
    page_title = "Sales"
    columns = (
        {"label": "Date", "field": "created_at"},
        {"label": "Hub", "field": "hub__name"},
        {"label": "Agent", "field": "agent__display_name"},
        {"label": "Customer", "field": "customer_name"},
        {"label": "Total", "field": "total"},
        {"label": "Status", "field": "status"},
    )
    search_fields = ("customer_name", "customer_phone", "payment_reference")
    date_filter_field = "created_at"
    create_url_name = "sales:create"
    create_label = "New sale"
    create_permission = "sales.add_sale"
    export_url_name = "sales:export"
    row_edit_url_name = "sales:edit"
    row_edit_permission = "sales.change_sale"


class SaleExportView(ScopedModelExportView):
    list_view_class = SaleListView


class SaleDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = Sale
    template_name = "sales/sale_detail.html"
    context_object_name = "sale"
    permission_required = "sales.view_sale"
    page_title = "Sale details"

    def get_queryset(self):
        return scope_queryset(
            Sale.objects.select_related("hub", "agent", "business", "created_by")
            .prefetch_related("items__product"),
            self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["item_columns"] = (
            {"label": "Product", "field": "product__name"},
            {"label": "Quantity", "field": "quantity"},
            {"label": "Unit price", "field": "unit_price"},
            {"label": "Line total", "field": "line_total"},
        )
        context["can_edit_sale"] = self.request.user.has_perm("sales.change_sale")
        return context


class SaleUpdateView(ProtectedUpdateView):
    model = Sale
    form_class = SaleUpdateForm
    page_title = "Edit sale details"
    success_url_name = "sales:list"
    cancel_url_name = "sales:list"

    def get_queryset(self):
        return scope_queryset(Sale.objects.all(), self.request.user)


class SaleCreateView(FormView):
    template_name = "components/record_form.html"
    form_class = SaleEntryForm
    page_title = "Record a sale"
    permission_required = "sales.add_sale"
    submit_label = "Complete sale"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        if not request.user.has_perm(self.permission_required):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        available_hubs = hubs_for_user(self.request.user, active_only=True)
        form.fields["hub"].queryset = available_hubs
        form.fields["business"].queryset = Business.objects.filter(
            status=Business.Status.ACTIVE, hub__in=available_hubs
        )
        return form

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            sale = complete_sale(
                hub=data["hub"],
                agent=self.request.user,
                items=[{"product": data["product"].pk, "quantity": data["quantity"]}],
                actor=self.request.user,
                customer_name=data["customer_name"],
                customer_phone=data["customer_phone"],
                payment_method=data["payment_method"],
                payment_reference=data["payment_reference"],
                notes=data["notes"],
                business=data.get("business"),
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f"Sale completed for {sale.total}.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("sales:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(page_title=self.page_title, submit_label=self.submit_label)
        return context


class SalesAgentListView(ScopedModelListView):
    model = User
    template_name = "components/record_list.html"
    page_title = "Sales agents"
    columns = (
        {"label": "Agent", "field": "display_name"},
        {"label": "Email", "field": "email"},
        {"label": "Phone", "field": "phone_number"},
    )
    search_fields = ("first_name", "last_name", "email", "username")
    permission_required = "sales.view_sale"

    def get_queryset(self):
        queryset = User.objects.filter(role=Role.SALES_AGENT, is_active=True).order_by("last_name", "first_name")
        if self.request.user.role not in (Role.SUPER_ADMIN, Role.ADMIN):
            hub_ids = hubs_for_user(self.request.user).values_list("pk", flat=True)
            queryset = queryset.filter(hub_memberships__hub_id__in=hub_ids, hub_memberships__is_active=True)
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
                | Q(username__icontains=query)
            )
        return queryset.distinct()