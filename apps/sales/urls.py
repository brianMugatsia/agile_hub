from django.urls import path

from .views import (
    SaleCreateView,
    SaleDetailView,
    SaleExportView,
    SaleListView,
    SalesAgentListView,
    SaleUpdateView,
)

app_name = "sales"

urlpatterns = [
    path("export/<str:file_format>/", SaleExportView.as_view(), name="export"),
    path("", SaleListView.as_view(), name="list"),
    path("create/", SaleCreateView.as_view(), name="create"),
    path("<uuid:pk>/edit/", SaleUpdateView.as_view(), name="edit"),
    path("agents/", SalesAgentListView.as_view(), name="agent_list"),
    path("<uuid:pk>/", SaleDetailView.as_view(), name="detail"),
]