from django.urls import path

from .views import (
    ApprovalInboxView,
    ApproveInboxCommissionView,
    ApproveInboxSalaryView,
    InventoryReconciliationView,
    ReportIndexView,
)

app_name = "reports"

urlpatterns = [
    path("", ReportIndexView.as_view(), name="index"),
    path(
        "inventory-reconciliation/",
        InventoryReconciliationView.as_view(),
        name="inventory_reconciliation",
    ),
    path("approvals/", ApprovalInboxView.as_view(), name="approvals"),
    path(
        "approvals/salaries/<int:pk>/approve/",
        ApproveInboxSalaryView.as_view(),
        name="approve_salary",
    ),
    path(
        "approvals/commissions/<int:pk>/approve/",
        ApproveInboxCommissionView.as_view(),
        name="approve_commission",
    ),
]