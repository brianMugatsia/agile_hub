from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.roles import Role
from apps.hubs.models import Hub
from apps.members.models import Business, MemberProfile
from apps.products.models import Product
from .models import Sale

User = get_user_model()


class SaleEntryForm(forms.Form):
    hub = forms.ModelChoiceField(queryset=Hub.objects.filter(status=Hub.Status.ACTIVE))
    seller_type = forms.ChoiceField(
        choices=[("agent", "Sales Agent"), ("member", "Hub Member")],
        initial="agent",
        widget=forms.RadioSelect,
    )
    agent = forms.ModelChoiceField(
        queryset=User.objects.filter(role=Role.SALES_AGENT, is_active=True),
        required=False,
    )
    member = forms.ModelChoiceField(
        queryset=MemberProfile.objects.select_related("user").all(),
        required=False,
    )
    business = forms.ModelChoiceField(
        queryset=Business.objects.filter(status=Business.Status.ACTIVE),
        required=False,
        label="Registered Customer / Outlet",
        help_text="Leave blank for Walk-in customer.",
    )
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_active=True))
    quantity = forms.IntegerField(min_value=1)
    customer_name = forms.CharField(max_length=160, required=False, help_text="Optional walk-in customer name")
    customer_phone = forms.CharField(max_length=24, required=False, help_text="Optional walk-in customer phone")
    payment_method = forms.ChoiceField(choices=[
        ("CASH", "Cash"),
        ("MOBILE_MONEY", "Mobile money"),
        ("BANK", "Bank transfer"),
        ("CREDIT", "Credit"),
    ])
    payment_reference = forms.CharField(max_length=80, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        cleaned_data = super().clean()
        seller_type = cleaned_data.get("seller_type")
        agent = cleaned_data.get("agent")
        member = cleaned_data.get("member")

        if seller_type == "agent":
            if not agent:
                raise forms.ValidationError({"agent": "Please select a sales agent."})
            cleaned_data["member"] = None
        elif seller_type == "member":
            if not member:
                raise forms.ValidationError({"member": "Please select a hub member."})
            cleaned_data["agent"] = None
        else:
            if not agent and not member:
                raise forms.ValidationError("Please select either a sales agent or a hub member as the seller.")
        return cleaned_data


class SaleUpdateForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ("customer_name", "customer_phone", "payment_reference", "notes")
