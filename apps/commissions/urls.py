from django.urls import path

from .views import (
    ApproveCommissionView,
    CommissionListView,
    PayCommissionView,
    RejectCommissionView,
    ReverseCommissionView,
)

app_name = "commissions"

urlpatterns = [
    path("", CommissionListView.as_view(), name="list"),
    path("<int:pk>/approve/", ApproveCommissionView.as_view(), name="approve"),
    path("<int:pk>/reject/", RejectCommissionView.as_view(), name="reject"),
    path("<int:pk>/pay/", PayCommissionView.as_view(), name="pay"),
    path("<int:pk>/reverse/", ReverseCommissionView.as_view(), name="reverse"),
]