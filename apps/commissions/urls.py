from django.urls import path

from .views import (
    ApproveCommissionView,
    AgentCommissionStatementView,
    ApprovedCommissionListView,
    CommissionDetailView,
    CommissionExportView,
    CommissionHubView,
    CommissionListView,
    CommissionSettingsView,
    PaidCommissionListView,
    PendingCommissionListView,
    PayCommissionView,
    RejectCommissionView,
    ReverseCommissionView,
    ServiceCommissionListView,
    ServiceCommissionDetailView,
    ApproveServiceCommissionView,
    RejectServiceCommissionView,
    PayServiceCommissionView,
    ReverseServiceCommissionView,
)

app_name = "commissions"

urlpatterns = [
    path("", CommissionHubView.as_view(), name="list"),
    path("agents/", CommissionListView.as_view(), name="agent_list"),
    path("pending/", PendingCommissionListView.as_view(), name="pending"),
    path("approved/", ApprovedCommissionListView.as_view(), name="approved"),
    path("paid/", PaidCommissionListView.as_view(), name="paid"),
    path("settings/", CommissionSettingsView.as_view(), name="settings"),
    path("agent/<uuid:agent_id>/statement/", AgentCommissionStatementView.as_view(), name="agent_statement"),

    path("export/<str:format>/", CommissionExportView.as_view(), name="export"),
    path("<int:pk>/", CommissionDetailView.as_view(), name="detail"),
    path("<int:pk>/approve/", ApproveCommissionView.as_view(), name="approve"),
    path("<int:pk>/reject/", RejectCommissionView.as_view(), name="reject"),
    path("<int:pk>/pay/", PayCommissionView.as_view(), name="pay"),
    path("<int:pk>/reverse/", ReverseCommissionView.as_view(), name="reverse"),
    # Service Commissions
    path("service-commissions/", ServiceCommissionListView.as_view(), name="service_list"),
    path("service-commissions/<int:pk>/", ServiceCommissionDetailView.as_view(), name="service_detail"),
    path("service-commissions/<int:pk>/approve/", ApproveServiceCommissionView.as_view(), name="service_approve"),
    path("service-commissions/<int:pk>/reject/", RejectServiceCommissionView.as_view(), name="service_reject"),
    path("service-commissions/<int:pk>/pay/", PayServiceCommissionView.as_view(), name="service_pay"),
    path("service-commissions/<int:pk>/reverse/", ReverseServiceCommissionView.as_view(), name="service_reverse"),
]
