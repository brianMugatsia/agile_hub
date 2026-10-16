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


def _member_choices(instance, user):
    accessible_hubs = hubs_for_user(user, active_only=True)
    queryset = MemberProfile.objects.filter(Q(hub__in=accessible_hubs) | Q(hub__isnull=True))
    if instance.pk and instance.member_id:
        queryset |= MemberProfile.objects.filter(pk=instance.member_id)
    return queryset.distinct()


class MemberProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")

    class Meta:
        model = MemberProfile
        fields = ["first_name", "last_name", "phone_number", "national_id", "address", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        if profile.user:
            profile.user.first_name = self.cleaned_data["first_name"]
            profile.user.last_name = self.cleaned_data["last_name"]
            if commit:
                profile.user.save()
        if commit:
            profile.save()
        return profile


class MemberCreateForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role="MEMBER", is_active=True).order_by("last_name", "first_name")
    )

    class Meta:
        model = MemberProfile
        fields = ["user", "hub", "phone_number", "national_id", "address", "notes"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["hub"].queryset = _hub_choices(self.fields["hub"], self.instance, user)
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
            self.fields["member"].queryset = _member_choices(self.instance, user)
        if user and user.role == Role.MEMBER:
            self.fields["member"].queryset = MemberProfile.objects.filter(user=user)