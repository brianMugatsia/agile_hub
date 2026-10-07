from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.urls import reverse
from django.views.generic import FormView

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.beneficiaries.models import Business
from apps.core.generic import ScopedModelListView, hubs_for_user
from apps.hubs.models import HubMembership
from apps.sales.services import complete_sale

from .forms import SaleEntryForm
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
    create_url_name = "sales:create"
    create_label = "Record sale"
    create_permission = "sales.add_sale"


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