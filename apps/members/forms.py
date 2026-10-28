from django import forms
from django.db.models import Q

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.hubs.permissions import hubs_for_user
from apps.services.models import ServiceType

from .models import MemberProfile, Business


CROP_CHOICES = [
    ("", "---------"),
    ("Maize", "Maize"),
    ("Beans", "Beans"),
    ("Coffee", "Coffee"),
    ("Tea", "Tea"),
    ("Horticulture", "Horticulture (Fruits & Veg)"),
    ("Wheat", "Wheat"),
    ("Rice", "Rice"),
    ("Sugarcane", "Sugarcane"),
    ("Potatoes", "Irish & Sweet Potatoes"),
    ("Cotton", "Cotton"),
    ("Other", "Other"),
]


def _hub_choices(field, instance, user):
    queryset = hubs_for_user(user, active_only=True).distinct()
    if instance.pk and instance.hub_id:
        queryset |= field.queryset.model.objects.filter(pk=instance.hub_id).distinct()
    return queryset


def _member_choices(instance, user):
    accessible_hubs = hubs_for_user(user, active_only=True)
    queryset = MemberProfile.objects.filter(
        customer_type=MemberProfile.CustomerType.FARMER
    ).filter(Q(hub__in=accessible_hubs) | Q(hub__isnull=True))
    if instance.pk and instance.member_id:
        queryset |= MemberProfile.objects.filter(pk=instance.member_id)
    return queryset.distinct()


class MemberProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")
    crops = forms.ChoiceField(
        choices=CROP_CHOICES,
        required=False,
        label="Primary Crop",
        widget=forms.Select(attrs={"class": "select"}),
    )
    services = forms.ModelMultipleChoiceField(
        queryset=ServiceType.objects.filter(is_active=True),
        required=False,
        label="Assigned Services (Select 1 or more)",
        widget=forms.CheckboxSelectMultiple(),
        help_text="Optional. Check one or more services provided or utilized by this member.",
    )

    class Meta:
        model = MemberProfile
        fields = [
            "first_name", "last_name", "phone_number",
            "national_id", "location", "crops", "services", "notes"
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.customer_type = MemberProfile.CustomerType.FARMER
        if profile.user:
            fn = self.cleaned_data.get("first_name", "")
            ln = self.cleaned_data.get("last_name", "")
            if fn or ln:
                profile.user.first_name = fn
                profile.user.last_name = ln
                if commit:
                    profile.user.save()
        if commit:
            profile.save()
            self.save_m2m()
        return profile


class MemberCreateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")
    email = forms.EmailField(required=False, label="Email")
    crops = forms.ChoiceField(
        choices=CROP_CHOICES,
        required=False,
        label="Primary Crop",
        widget=forms.Select(attrs={"class": "select"}),
    )
    services = forms.ModelMultipleChoiceField(
        queryset=ServiceType.objects.filter(is_active=True),
        required=False,
        label="Assigned Services (Select 1 or more)",
        widget=forms.CheckboxSelectMultiple(),
        help_text="Optional. Check one or more services provided or utilized by this member.",
    )

    class Meta:
        model = MemberProfile
        fields = [
            "first_name", "last_name", "email",
            "hub", "phone_number", "national_id", "location", "crops", "services", "notes"
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["hub"].queryset = _hub_choices(self.fields["hub"], self.instance, user)

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.customer_type = MemberProfile.CustomerType.FARMER
        email = self.cleaned_data.get("email", "").strip().lower()

        if email:
            username = email
            base_username = email.split("@")[0]
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            new_user = User.objects.create_user(
                username=username,
                email=email,
                first_name=self.cleaned_data.get("first_name", ""),
                last_name=self.cleaned_data.get("last_name", ""),
                phone_number=self.cleaned_data.get("phone_number", ""),
                role=Role.MEMBER,
                is_active=True,
            )
            profile.user = new_user
        else:
            profile.name = f"{self.cleaned_data.get('first_name', '')} {self.cleaned_data.get('last_name', '')}".strip()

        if commit:
            profile.save()
            self.save_m2m()
        return profile


class CustomerForm(forms.ModelForm):
    name = forms.CharField(max_length=160, label="Customer Name")
    customer_type = forms.ChoiceField(
        choices=MemberProfile.CustomerType.choices,
        label="Category / Type",
        widget=forms.Select(attrs={"class": "select"}),
    )
    crops = forms.ChoiceField(
        choices=CROP_CHOICES,
        required=False,
        label="Primary Crop",
        widget=forms.Select(attrs={"class": "select"}),
    )

    class Meta:
        model = MemberProfile
        fields = [
            "customer_type", "name", "phone_number", "national_id",
            "location", "crops", "hub", "loop_feedback", "notes"
        ]
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and not self.initial.get("name"):
            self.initial["name"] = self.instance.display_name
        if user:
            self.fields["hub"].queryset = _hub_choices(self.fields["hub"], self.instance, user)

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if profile.user and "name" in self.cleaned_data:
            name_parts = self.cleaned_data["name"].strip().split(" ", 1)
            profile.user.first_name = name_parts[0]
            profile.user.last_name = name_parts[1] if len(name_parts) > 1 else ""
            profile.user.save(update_fields=["first_name", "last_name"])
        return profile


class BusinessForm(forms.ModelForm):
    name = forms.CharField(
        label="Contribution Name",
        widget=forms.TextInput(attrs={"placeholder": "Enter contribution name"})
    )

    class Meta:
        model = Business
        fields = [
            "member", "hub", "name",
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
