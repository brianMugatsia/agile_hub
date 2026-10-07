from django import forms

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.hubs.permissions import hubs_for_user

from .models import BeneficiaryProfile, Business


class BeneficiaryProfileForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role="BENEFICIARY", is_active=True).order_by("last_name", "first_name")
    )

    class Meta:
        model = BeneficiaryProfile
        fields = ["user", "hub", "phone_number", "national_id", "address", "notes"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["hub"].queryset = hubs_for_user(user, active_only=True)
        if user and user.role == Role.BENEFICIARY:
            self.fields["user"].queryset = User.objects.filter(pk=user.pk, role=Role.BENEFICIARY)


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = [
            "beneficiary", "hub", "name", "business_type", "registration_number",
            "phone_number", "address", "status",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["hub"].queryset = hubs_for_user(user, active_only=True)
        if user and user.role == Role.BENEFICIARY:
            self.fields["beneficiary"].queryset = BeneficiaryProfile.objects.filter(user=user)