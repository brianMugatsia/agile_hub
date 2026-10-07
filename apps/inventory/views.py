from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.views.generic import FormView

from apps.core.generic import ScopedModelListView, hubs_for_user
from apps.inventory.services import record_movement

from .forms import StockMovementForm
from .models import InventoryTransaction


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
    create_url_name = "inventory:movement_create"
    create_label = "Record movement"
    create_permission = "inventory.add_inventorytransaction"


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