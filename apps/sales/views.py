from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.accounts.forms import UserCreateForm
from apps.accounts.services import create_user_from_form, sync_user_group
from apps.members.models import Business
from apps.core.generic import ProtectedUpdateView, ScopedModelListView, hubs_for_user
from apps.core.exports import ScopedModelExportView
from apps.core.mixins import PageMixin
from apps.core.scoping import scope_queryset
from apps.core.spreadsheets import SpreadsheetImportView, ExcelTemplateView
from apps.core.models import StagedSpreadsheetImport
from apps.hubs.permissions import selected_hub
from apps.sales.services import complete_sale

from .forms import SaleEntryForm, SaleUpdateForm
from .models import Sale


class SaleListView(ScopedModelListView):
    model = Sale
    page_title = "Sales"
    columns = (
        {"label": "Date", "field": "created_at"},
        {"label": "Agent / Member", "field": "seller_display"},
        {"label": "Customer", "field": "customer_display"},
        {"label": "Total", "field": "total"},
        {"label": "Status", "field": "status"},
    )
    search_fields = ("customer_name", "customer_phone", "payment_reference", "notes", "agent__first_name", "agent__last_name", "member__name", "member__user__first_name", "member__user__last_name", "business__name", "hub__name")
    date_filter_field = "created_at"
    create_url_name = "sales:create"
    create_label = "New sale"
    create_permission = "sales.add_sale"
    export_url_name = "sales:export"
    row_edit_url_name = "sales:edit"
    row_edit_permission = "sales.change_sale"
    filter_hub = True

    def get_context_data(self, **kwargs):
        user = self.request.user
        is_platform_admin = user.role in (Role.SUPER_ADMIN, Role.ADMIN)
        available_hubs, active_hub, hub_error = selected_hub(self.request)
        show_hub_column = is_platform_admin and not self.selected_hub and not active_hub
        cols = [{"label": "Date", "field": "created_at"}]
        if show_hub_column:
            cols.append({"label": "Hub", "field": "hub__name"})
        cols.extend([
            {"label": "Agent / Member", "field": "seller_display"},
            {"label": "Customer", "field": "customer_display"},
            {"label": "Total", "field": "total"},
            {"label": "Status", "field": "status"},
        ])
        self.columns = tuple(cols)
        return super().get_context_data(**kwargs)


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
            Sale.objects.select_related("hub", "agent", "member", "business", "created_by")
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
    template_name = "sales/sale_form.html"
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
                agent=data.get("agent"),
                member=data.get("member"),
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
        {"label": "Hub", "field": "hub__name"},
    )
    search_fields = ("first_name", "last_name", "email", "username")
    permission_required = "sales.view_sale"
    create_url_name = "sales:agent_create"
    create_label = "Add sales agent"
    create_permission = "accounts.add_user"
    import_url_name = "sales:agent_import"
    import_permission = "accounts.add_user"
    row_edit_url_name = "accounts:user_edit"
    row_edit_permission = "accounts.change_user"
    filter_hub = True
    hub_filter_paths = ("hub_memberships__hub_id",)

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            role=Role.SALES_AGENT, is_active=True
        ).order_by("last_name", "first_name")
        if self.request.user.role not in (Role.SUPER_ADMIN, Role.ADMIN):
            hub_ids = hubs_for_user(self.request.user).values_list("pk", flat=True)
            queryset = queryset.filter(Q(hub_memberships__hub_id__in=hub_ids, hub_memberships__is_active=True) | Q(hub_id__in=hub_ids))
        return queryset.distinct()


class SalesAgentCreateView(PermissionRequiredMixin, PageMixin, FormView):
    permission_required = "accounts.add_user"
    form_class = UserCreateForm
    template_name = "sales/agent_form.html"
    page_title = "Add sales agent"
    breadcrumbs = (("Sales agents", reverse_lazy("sales:agent_list")), ("New sales agent", None))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["role"].choices = [(Role.SALES_AGENT, "Sales Agent")]
        form.fields["role"].initial = Role.SALES_AGENT
        form.fields["role"].widget = forms.HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submit_label"] = "Create sales agent"
        context["multipart"] = False
        return context

    def form_valid(self, form):
        form.cleaned_data["role"] = Role.SALES_AGENT
        user = create_user_from_form(form, actor=self.request.user, request=self.request)
        user.role = Role.SALES_AGENT
        user.save()
        messages.success(self.request, f"{user.display_name} was created as a sales agent.")
        return redirect("sales:agent_list")


class SalesAgentImportView(SpreadsheetImportView):
    import_type = StagedSpreadsheetImport.ImportType.SALES_AGENTS
    permission_required = "accounts.add_user"
    list_url = "sales:agent_list"
    template_url = "sales:agent_import_template"
    page_title = "Import sales agents"
    description = "Create sales agents from a validated Excel workbook."
    required_headers = ("username", "first_name", "last_name")
    template_headers = ("username", "email", "first_name", "last_name", "phone_number")

    def validate_rows(self, rows, user):
        errors = []
        accepted = []
        usernames = {
            str(row["values"].get("username", "")).strip().casefold()
            for row in rows
            if row["values"].get("username")
        }
        default_hub = getattr(user, "hub", None) or hubs_for_user(user, active_only=True).first()
        existing_users = {
            u.normalized_username: u
            for u in User.objects.annotate(normalized_username=Lower("username"))
            .filter(normalized_username__in=usernames)
        }
        seen_usernames = set()
        for row in rows:
            data = row["values"]
            username = str(data.get("username", "")).strip()
            email = str(data.get("email", "")).strip()
            if not username and email:
                username = email.split("@")[0]
            if not username:
                errors.append(f"Row {row['line']}: Username or email is required.")
                continue
            if username.casefold() in seen_usernames:
                errors.append(f"Row {row['line']}: Username {username} is duplicated in this workbook.")
                continue
            seen_usernames.add(username.casefold())

            first_name = str(data.get("first_name", "")).strip()
            last_name = str(data.get("last_name", "")).strip()
            if not first_name or not last_name:
                errors.append(f"Row {row['line']}: First name and last name are required.")
                continue

            existing_user = existing_users.get(username.casefold())
            if existing_user:
                errors.append(f"Row {row['line']}: User already exists with username {username}.")
                continue

            accepted.append({
                "line": row["line"],
                "username": username,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": str(data.get("phone_number", "")).strip(),
                "hub_id": default_hub.pk if default_hub else None,
            })
        return accepted, errors

    @transaction.atomic
    def commit_rows(self, accepted, user):
        created_count = 0
        for item in accepted:
            new_user = User.objects.create_user(
                username=item["username"],
                email=item["email"],
                password=User.objects.make_random_password(),
                first_name=item["first_name"],
                last_name=item["last_name"],
                phone_number=item["phone_number"],
                role=Role.SALES_AGENT,
                hub_id=item["hub_id"],
            )
            sync_user_group(new_user)
            created_count += 1
        messages.success(self.request, f"Successfully imported {created_count} sales agents.")


class SalesAgentImportTemplateView(ExcelTemplateView):
    permission_required = "accounts.add_user"
    filename = "sales_agents_import_template.xlsx"
    headers = ("username", "email", "first_name", "last_name", "phone_number")
