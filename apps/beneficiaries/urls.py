from django.urls import path

from .views import BeneficiaryCreateView, BeneficiaryListView, BusinessCreateView, BusinessListView

app_name = "beneficiaries"

urlpatterns = [
    path("", BeneficiaryListView.as_view(), name="list"),
    path("create/", BeneficiaryCreateView.as_view(), name="create"),
    path("businesses/", BusinessListView.as_view(), name="businesses"),
    path("businesses/create/", BusinessCreateView.as_view(), name="business_create"),
]