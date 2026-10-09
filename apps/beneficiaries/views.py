from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView

from apps.core.generic import ProtectedCreateView, ProtectedUpdateView, ScopedModelListView
from apps.core.mixins import ActiveHubInitialMixin, PageMixin
from apps.core.scoping import scope_queryset

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
    create_label = "Add beneficiary"
    create_permission = "beneficiaries.add_beneficiaryprofile"
    row_edit_url_name = "beneficiaries:edit"
    row_edit_permission = "beneficiaries.change_beneficiaryprofile"
    filter_hub = True


class BeneficiaryDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = BeneficiaryProfile
    template_name = "beneficiaries/beneficiary_detail.html"
    context_object_name = "beneficiary"
    permission_required = "beneficiaries.view_beneficiaryprofile"
    page_title = "Beneficiary details"

    def get_queryset(self):
        return scope_queryset(
            BeneficiaryProfile.objects.select_related("user", "hub"),
            self.request.user,
        )

    def get_breadcrumbs(self):
        return [
            ("Beneficiaries", reverse("beneficiaries:list")),
            (self.object.user.display_name, None),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            businesses=scope_queryset(
                self.object.businesses.all(), self.request.user
            ).select_related("hub"),
            business_columns=(
                {"label": "Business", "field": "name"},
                {"label": "Type", "field": "business_type"},
                {"label": "Hub", "field": "hub__name"},
                {"label": "Status", "field": "status"},
            ),
            can_edit_beneficiary=self.request.user.has_perm(
                "beneficiaries.change_beneficiaryprofile"
            ),
            can_add_business=self.request.user.has_perm("beneficiaries.add_business"),
            row_edit_url_name="beneficiaries:business_edit",
            can_edit_rows=self.request.user.has_perm("beneficiaries.change_business"),
        )
        return context


class BeneficiaryUpdateView(ProtectedUpdateView):
    model = BeneficiaryProfile
    form_class = BeneficiaryProfileForm
    page_title = "Edit beneficiary"
    success_url_name = "beneficiaries:list"
    cancel_url_name = "beneficiaries:list"

    def get_queryset(self):
        return scope_queryset(BeneficiaryProfile.objects.all(), self.request.user)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class BeneficiaryCreateView(ActiveHubInitialMixin, ProtectedCreateView):
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
    create_url_name = "beneficiaries:business_create"
    create_label = "Add business"
    create_permission = "beneficiaries.add_business"
    row_edit_url_name = "beneficiaries:business_edit"
    row_edit_permission = "beneficiaries.change_business"
    filter_hub = True


class BusinessCreateView(ActiveHubInitialMixin, ProtectedCreateView):
    model = Business
    form_class = BusinessForm
    page_title = "Add business"
    success_url_name = "beneficiaries:businesses"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class BusinessUpdateView(ProtectedUpdateView):
    model = Business
    form_class = BusinessForm
    page_title = "Edit business"
    success_url_name = "beneficiaries:businesses"
    cancel_url_name = "beneficiaries:businesses"

    def get_queryset(self):
        return scope_queryset(Business.objects.all(), self.request.user)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}