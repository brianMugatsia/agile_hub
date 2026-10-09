from django.urls import path

from .views import (
    LowStockReportView,
    ProductCreateView,
    ProductDetailView,
    ProductExportView,
    ProductListView,
    ProductPriceHistoryView,
    ProductUpdateView,
)
from apps.core.spreadsheets import ProductImportTemplateView, ProductImportView

app_name = "products"

urlpatterns = [
    path("import/", ProductImportView.as_view(), name="import"),
    path("import/template.xlsx", ProductImportTemplateView.as_view(), name="import_template"),
    path("export/<str:file_format>/", ProductExportView.as_view(), name="export"),
    path("low-stock/", LowStockReportView.as_view(), name="low_stock_report"),
    path("", ProductListView.as_view(), name="list"),
    path("create/", ProductCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", ProductUpdateView.as_view(), name="edit"),
    path("<int:pk>/price-history/", ProductPriceHistoryView.as_view(), name="price_history"),
    path("<int:pk>/", ProductDetailView.as_view(), name="detail"),
]