from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Exists, F, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView

from apps.core.generic import ProtectedCreateView, ProtectedUpdateView, ScopedModelListView
from apps.core.exports import ScopedModelExportView
from apps.core.spreadsheets import ProductImportTemplateView, ProductImportView
from apps.core.mixins import PageMixin
from apps.hubs.permissions import selected_hub
from apps.inventory.models import InventoryBalance

from .forms import ProductForm, ProductUpdateForm
from .models import Product, ProductPriceHistory


class ProductListView(ScopedModelListView):
    model = Product
    page_title = "Products"
    columns = (
        {"label": "SKU", "field": "sku"},
        {"label": "Product", "field": "name"},
        {"label": "Category", "field": "category"},
        {"label": "Unit price", "field": "selling_price"},
        {"label": "Stock", "field": "stock_on_hand"},
    )
    search_fields = ("sku", "name", "category")
    create_url_name = "products:create"
    create_permission = "products.add_product"
    row_edit_url_name = "products:edit"
    row_edit_permission = "products.change_product"
    filter_hub = True
    hub_filter_paths = ()
    export_url_name = "products:export"
    import_url_name = "products:import"
    import_permission = "products.add_product"

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.selected_hub:
            # Products carried by the selected hub. A product that no hub stocks yet
            # (for example one just created) stays visible so it can be stocked.
            stocked_here = InventoryBalance.objects.filter(
                hub=self.selected_hub, product_id=OuterRef("pk")
            )
            stocked_anywhere = InventoryBalance.objects.filter(product_id=OuterRef("pk"))
            queryset = queryset.filter(Exists(stocked_here) | ~Exists(stocked_anywhere))

            balance = InventoryBalance.objects.filter(
                hub=self.selected_hub,
                product_id=OuterRef("pk"),
            ).values("quantity")[:1]
            queryset = queryset.annotate(
                selected_hub_stock=Coalesce(
                    Subquery(balance, output_field=IntegerField()),
                    Value(0),
                    output_field=IntegerField(),
                )
            )
            self.columns = (
                {"label": "SKU", "field": "sku"},
                {"label": "Product", "field": "name"},
                {"label": "Category", "field": "category"},
                {"label": "Unit price", "field": "selling_price"},
                {"label": f"Stock at {self.selected_hub.name}", "field": "selected_hub_stock"},
            )
        else:
            self.columns = (
                {"label": "SKU", "field": "sku"},
                {"label": "Product", "field": "name"},
                {"label": "Category", "field": "category"},
                {"label": "Unit price", "field": "selling_price"},
                {"label": "Stock across hubs", "field": "stock_on_hand"},
            )
        return queryset


class ProductExportView(ScopedModelExportView):
    list_view_class = ProductListView


class ProductCreateView(ProtectedCreateView):
    model = Product
    form_class = ProductForm
    page_title = "Add product"
    success_url_name = "products:list"


class ProductUpdateView(ProtectedUpdateView):
    model = Product
    form_class = ProductUpdateForm
    page_title = "Edit product"
    success_url_name = "products:list"
    cancel_url_name = "products:list"

    @transaction.atomic
    def form_valid(self, form):
        previous_price = Product.objects.select_for_update().values_list(
            "selling_price", flat=True
        ).get(pk=self.object.pk)
        response = super().form_valid(form)
        if previous_price != self.object.selling_price:
            ProductPriceHistory.objects.create(
                product=self.object,
                previous_price=previous_price,
                new_price=self.object.selling_price,
                changed_by=self.request.user,
                reason=form.cleaned_data["price_change_reason"].strip(),
            )
        return response


class ProductDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"
    permission_required = "products.view_product"
    page_title = "Product details"


class ProductPriceHistoryView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, TemplateView):
    template_name = "products/price_history.html"
    permission_required = "products.view_productpricehistory"
    page_title = "Product price history"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = get_object_or_404(Product, pk=self.kwargs["pk"])
        context.update(
            product=product,
            price_history=ProductPriceHistory.objects.filter(product=product).select_related(
                "changed_by"
            ),
            columns=(
                {"label": "Changed", "field": "changed_at"},
                {"label": "Previous price", "field": "previous_price"},
                {"label": "New price", "field": "new_price"},
                {"label": "Changed by", "field": "changed_by__display_name"},
                {"label": "Reason", "field": "reason"},
            ),
        )
        return context


class LowStockReportView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, TemplateView):
    template_name = "products/low_stock_report.html"
    permission_required = "products.view_product"
    page_title = "Low stock report"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        available_hubs, selected, hub_error = selected_hub(self.request)
        balances = InventoryBalance.objects.filter(
            hub__in=available_hubs.filter(status="ACTIVE"),
            product__is_active=True,
            product__reorder_level__gt=0,
            quantity__lte=F("product__reorder_level"),
        ).select_related("hub", "product").order_by("hub__name", "product__name")
        if selected:
            balances = balances.filter(hub=selected)
        elif hub_error:
            balances = balances.none()
        context.update(
            low_stock_products=balances,
            filter_hubs=available_hubs,
            selected_hub=selected.pk if selected else "",
            hub_error=hub_error,
            columns=(
                {"label": "Hub", "field": "hub__name"},
                {"label": "SKU", "field": "product__sku"},
                {"label": "Product", "field": "product__name"},
                {"label": "On hand", "field": "quantity"},
                {"label": "Reorder level", "field": "product__reorder_level"},
            ),
        )
        return context