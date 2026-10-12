from django.urls import path

from .views import (
    ApproveCommissionView,
    AgentCommissionStatementView,
    ApprovedCommissionListView,
    CommissionExportView,
    CommissionDetailView,
    CommissionListView,
    CommissionSettingsView,
    PaidCommissionListView,
    PayCommissionView,
    PendingCommissionListView,
    RejectCommissionView,
    ReverseCommissionView,
)

app_name = "commissions"

urlpatterns = [
    path("export/<str:file_format>/", CommissionExportView.as_view(), name="export"),
    path("settings/", CommissionSettingsView.as_view(), name="settings"),
    path("agents/<uuid:agent_id>/statement/", AgentCommissionStatementView.as_view(), name="agent_statement"),
    path("pending/", PendingCommissionListView.as_view(), name="pending"),
    path("approved/", ApprovedCommissionListView.as_view(), name="approved"),
    path("paid/", PaidCommissionListView.as_view(), name="paid"),
    path("", CommissionListView.as_view(), name="list"),
    path("<int:pk>/", CommissionDetailView.as_view(), name="detail"),
    path("<int:pk>/approve/", ApproveCommissionView.as_view(), name="approve"),
    path("<int:pk>/reject/", RejectCommissionView.as_view(), name="reject"),
    path("<int:pk>/pay/", PayCommissionView.as_view(), name="pay"),
    path("<int:pk>/reverse/", ReverseCommissionView.as_view(), name="reverse"),
]