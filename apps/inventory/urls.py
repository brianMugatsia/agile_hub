from django.urls import path

from .views import (
    InventoryExportView,
    InventoryListView,
    PurchaseOrderCreateView,
    PurchaseOrderListView,
    PurchaseOrderReceiveView,
    StockMovementCreateView,
    SupplierCreateView,
    SupplierListView,
)
from apps.core.spreadsheets import InventoryImportTemplateView, InventoryImportView

app_name = "inventory"

urlpatterns = [
    path("purchase-orders/", PurchaseOrderListView.as_view(), name="purchase_orders"),
    path("purchase-orders/create/", PurchaseOrderCreateView.as_view(), name="purchase_order_create"),
    path("purchase-orders/<int:pk>/receive/", PurchaseOrderReceiveView.as_view(), name="purchase_order_receive"),
    path("suppliers/", SupplierListView.as_view(), name="suppliers"),
    path("suppliers/create/", SupplierCreateView.as_view(), name="supplier_create"),
    path("import/", InventoryImportView.as_view(), name="import"),
    path("import/template.xlsx", InventoryImportTemplateView.as_view(), name="import_template"),
    path("export/<str:file_format>/", InventoryExportView.as_view(), name="export"),
    path("", InventoryListView.as_view(), name="list"),
    path("movement/create/", StockMovementCreateView.as_view(), name="movement_create"),
]