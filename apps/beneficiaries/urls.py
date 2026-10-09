from django.urls import path

from .views import (
    BeneficiaryCreateView,
    BeneficiaryDetailView,
    BeneficiaryListView,
    BeneficiaryUpdateView,
    BusinessCreateView,
    BusinessListView,
    BusinessUpdateView,
)

app_name = "beneficiaries"

urlpatterns = [
    path("", BeneficiaryListView.as_view(), name="list"),
    path("create/", BeneficiaryCreateView.as_view(), name="create"),
    path("<int:pk>/", BeneficiaryDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", BeneficiaryUpdateView.as_view(), name="edit"),
    path("businesses/", BusinessListView.as_view(), name="businesses"),
    path("businesses/create/", BusinessCreateView.as_view(), name="business_create"),
    path("businesses/<int:pk>/edit/", BusinessUpdateView.as_view(), name="business_edit"),
]