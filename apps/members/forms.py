from django import forms
from django.db.models import Q

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.hubs.permissions import hubs_for_user

from .models import MemberProfile, Business


def _hub_choices(field, instance, user):
    queryset = hubs_for_user(user, active_only=True).distinct()
    if instance.pk and instance.hub_id:
        queryset |= field.queryset.model.objects.filter(pk=instance.hub_id).distinct()
    return queryset


class MemberProfileForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role="MEMBER", is_active=True).order_by("last_name", "first_name")
    )

    class Meta:
        model = MemberProfile
        fields = ["user", "hub", "phone_number", "national_id", "address", "notes"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["user"].queryset = User.objects.filter(
                Q(role=Role.MEMBER, is_active=True) | Q(pk=self.instance.user_id)
            )
        if user:
            self.fields["hub"].queryset = _hub_choices(self.fields["hub"], self.instance, user)
        if user and user.role == Role.MEMBER:
            self.fields["user"].queryset = User.objects.filter(pk=user.pk, role=Role.MEMBER)


class MemberCreateForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role="MEMBER", is_active=True).order_by("last_name", "first_name")
    )

    class Meta:
        model = MemberProfile
        fields = ["user", "phone_number", "national_id", "address", "notes"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.role == Role.MEMBER:
            self.fields["user"].queryset = User.objects.filter(pk=user.pk, role=Role.MEMBER)


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = [
            "member", "hub", "name", "business_type", "registration_number",
            "phone_number", "address", "amount", "is_paid", "status",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].required = False
        self.fields["is_paid"].required = False
        if user:
            self.fields["hub"].queryset = _hub_choices(self.fields["hub"], self.instance, user)
        if user and user.role == Role.MEMBER:
            self.fields["member"].queryset = MemberProfile.objects.filter(user=user)