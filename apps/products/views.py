from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView

from apps.core.generic import ProtectedCreateView, ScopedModelListView
from apps.core.exports import ScopedModelExportView
from apps.core.spreadsheets import ProductImportTemplateView, ProductImportView
from apps.core.mixins import PageMixin
from apps.hubs.permissions import hubs_for_user
from apps.inventory.models import InventoryBalance

from .forms import ProductForm
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
    export_url_name = "products:export"
    import_url_name = "products:import"
    import_permission = "products.add_product"


class ProductExportView(ScopedModelExportView):
    list_view_class = ProductListView


class ProductCreateView(ProtectedCreateView):
    model = Product
    form_class = ProductForm
    page_title = "Add product"
    success_url_name = "products:list"


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
        balances = InventoryBalance.objects.filter(
            hub__in=hubs_for_user(self.request.user, active_only=True),
            product__is_active=True,
            product__reorder_level__gt=0,
            quantity__lte=F("product__reorder_level"),
        ).select_related("hub", "product").order_by("hub__name", "product__name")
        context.update(
            low_stock_products=balances,
            columns=(
                {"label": "Hub", "field": "hub__name"},
                {"label": "SKU", "field": "product__sku"},
                {"label": "Product", "field": "product__name"},
                {"label": "On hand", "field": "quantity"},
                {"label": "Reorder level", "field": "product__reorder_level"},
            ),
        )
        return context