from apps.core.generic import ProtectedCreateView, ScopedModelListView

from .forms import BeneficiaryProfileForm, BusinessForm
from .models import BeneficiaryProfile, Business


class BeneficiaryListView(ScopedModelListView):
    model = BeneficiaryProfile
    page_title = "Beneficiaries"
    columns = (
        {"label": "Name", "field": "user__display_name"},
        {"label": "Email", "field": "user__email"},
        {"label": "Phone", "field": "phone_number"},
        {"label": "Hub", "field": "hub__name"},
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "phone_number")
    create_url_name = "beneficiaries:create"
    create_permission = "beneficiaries.add_beneficiaryprofile"


class BeneficiaryCreateView(ProtectedCreateView):
    model = BeneficiaryProfile
    form_class = BeneficiaryProfileForm
    page_title = "Add beneficiary"
    success_url_name = "beneficiaries:list"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class BusinessListView(ScopedModelListView):
    model = Business
    page_title = "Businesses"
    columns = (
        {"label": "Business", "field": "name"},
        {"label": "Beneficiary", "field": "beneficiary__user__display_name"},
        {"label": "Hub", "field": "hub__name"},
        {"label": "Type", "field": "business_type"},
        {"label": "Status", "field": "status"},
    )
    search_fields = ("name", "business_type", "registration_number")


class BusinessCreateView(ProtectedCreateView):
    model = Business
    form_class = BusinessForm
    page_title = "Add business"
    success_url_name = "beneficiaries:businesses"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}