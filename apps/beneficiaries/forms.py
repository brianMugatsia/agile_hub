from django import forms
from django.db.models import Q

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.hubs.permissions import hubs_for_user

from .models import BeneficiaryProfile, Business


def _hub_choices(field, instance, user):
    queryset = hubs_for_user(user, active_only=True).distinct()
    if instance.pk and instance.hub_id:
        queryset |= field.queryset.model.objects.filter(pk=instance.hub_id).distinct()
    return queryset


class BeneficiaryProfileForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role="BENEFICIARY", is_active=True).order_by("last_name", "first_name")
    )

    class Meta:
        model = BeneficiaryProfile
        fields = ["user", "hub", "phone_number", "national_id", "address", "notes"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["user"].queryset = User.objects.filter(
                Q(role=Role.BENEFICIARY, is_active=True) | Q(pk=self.instance.user_id)
            )
        if user:
            self.fields["hub"].queryset = _hub_choices(self.fields["hub"], self.instance, user)
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
            self.fields["hub"].queryset = _hub_choices(self.fields["hub"], self.instance, user)
        if user and user.role == Role.BENEFICIARY:
            self.fields["beneficiary"].queryset = BeneficiaryProfile.objects.filter(user=user)