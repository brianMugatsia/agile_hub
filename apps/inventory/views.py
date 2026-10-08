from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import FormView, ListView
from django.views import View

from apps.core.exports import ScopedModelExportView
from apps.core.generic import ProtectedCreateView, ScopedModelListView, hubs_for_user
from apps.core.mixins import PageMixin
from apps.core.spreadsheets import InventoryImportTemplateView, InventoryImportView
from apps.inventory.services import (
    create_reorder_order,
    receive_purchase_order,
    record_movement,
)

from .forms import (
    PurchaseOrderReceiveForm,
    ReorderOrderForm,
    StockMovementForm,
    SupplierForm,
)
from .models import InventoryTransaction, PurchaseOrder, Supplier


class InventoryListView(ScopedModelListView):
    model = InventoryTransaction
    page_title = "Inventory movements"
    columns = (
        {"label": "Date", "field": "created_at"},
        {"label": "Hub", "field": "hub__name"},
        {"label": "Product", "field": "product__name"},
        {"label": "Type", "field": "kind"},
        {"label": "Direction", "field": "direction"},
        {"label": "Quantity", "field": "quantity"},
        {"label": "Reference", "field": "reference"},
    )
    search_fields = ("product__name", "product__sku", "reference")
    date_filter_field = "created_at"
    filter_fields = (
        ("kind", InventoryTransaction.Kind.choices),
        ("direction", InventoryTransaction.Direction.choices),
    )
    filter_hub = True
    create_url_name = "inventory:movement_create"
    create_label = "Record movement"
    create_permission = "inventory.add_inventorytransaction"
    export_url_name = "inventory:export"
    import_url_name = "inventory:import"
    import_permission = "inventory.add_inventorytransaction"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_create_purchase_order"] = self.request.user.has_perm(
            "inventory.add_purchaseorder"
        )
        return context


class InventoryExportView(ScopedModelExportView):
    list_view_class = InventoryListView


class SupplierListView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, ListView):
    model = Supplier
    template_name = "inventory/supplier_list.html"
    context_object_name = "suppliers"
    permission_required = "inventory.view_supplier"
    page_title = "Suppliers"

    def get_queryset(self):
        return Supplier.objects.filter(is_active=True)


class SupplierCreateView(ProtectedCreateView):
    model = Supplier
    form_class = SupplierForm
    permission_required = "inventory.add_supplier"
    page_title = "Add supplier"
    success_url_name = "inventory:suppliers"


class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, ListView):
    model = PurchaseOrder
    template_name = "inventory/purchase_order_list.html"
    context_object_name = "orders"
    permission_required = "inventory.view_purchaseorder"
    page_title = "Purchase orders"
    paginate_by = 25

    def get_queryset(self):
        return (
            PurchaseOrder.objects.filter(hub__in=hubs_for_user(self.request.user))
            .select_related("hub", "supplier", "created_by")
            .prefetch_related("lines__product")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_create_order"] = self.request.user.has_perm("inventory.add_purchaseorder")
        return context


class PurchaseOrderCreateView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, FormView):
    template_name = "inventory/purchase_order_form.html"
    form_class = ReorderOrderForm
    permission_required = "inventory.add_purchaseorder"
    page_title = "Create reorder purchase order"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}

    def form_valid(self, form):
        try:
            order = create_reorder_order(
                hub=form.cleaned_data["hub"],
                supplier=form.cleaned_data["supplier"],
                actor=self.request.user,
                notes=form.cleaned_data["notes"],
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f"Created purchase order #{order.pk}.")
        return redirect("inventory:purchase_orders")


class PurchaseOrderReceiveView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, View):
    permission_required = "inventory.change_purchaseorder"
    template_name = "inventory/purchase_order_receive.html"
    page_title = "Receive purchase order"

    def get_order(self, request, pk):
        return get_object_or_404(
            PurchaseOrder.objects.filter(hub__in=hubs_for_user(request.user))
            .select_related("hub", "supplier")
            .prefetch_related("lines__product"),
            pk=pk,
        )

    def get(self, request, pk):
        order = self.get_order(request, pk)
        return render(
            request,
            self.template_name,
            {
                "page_title": self.page_title,
                "order": order,
                "form": PurchaseOrderReceiveForm(order=order),
            },
        )

    def post(self, request, pk):
        order = self.get_order(request, pk)
        form = PurchaseOrderReceiveForm(request.POST, order=order)
        if form.is_valid():
            try:
                receive_purchase_order(
                    order_id=order.pk,
                    quantities=form.received_quantities(),
                    actor=request.user,
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, f"Received stock against purchase order #{order.pk}.")
                return redirect("inventory:purchase_orders")
        return render(
            request,
            self.template_name,
            {"page_title": self.page_title, "order": order, "form": form},
            status=400,
        )


class StockMovementCreateView(FormView):
    template_name = "components/record_form.html"
    form_class = StockMovementForm
    page_title = "Record stock movement"
    permission_required = "inventory.add_inventorytransaction"
    submit_label = "Save movement"

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
        form.fields["hub"].queryset = hubs_for_user(self.request.user, active_only=True)
        return form

    def form_valid(self, form):
        try:
            record_movement(
                actor=self.request.user,
                **form.cleaned_data,
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, "Inventory movement recorded.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("inventory:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(page_title=self.page_title, submit_label=self.submit_label)
        return context