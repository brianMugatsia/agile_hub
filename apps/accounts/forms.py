from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserChangeForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError

from .models import User
from .roles import Role, role_choices_for


class StyledFormMixin:
    """Applies the design-system CSS classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            css = self._css_class(widget)
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()
            if field.help_text:
                widget.attrs.setdefault("aria-describedby", f"id_{name}_helptext")

    @staticmethod
    def _css_class(widget):
        if isinstance(widget, forms.CheckboxInput):
            return "checkbox__input"
        if isinstance(widget, (forms.Select, forms.SelectMultiple)):
            return "select"
        if isinstance(widget, forms.Textarea):
            return "textarea"
        if isinstance(widget, forms.FileInput):
            return "file-input"
        return "input"


class UniqueEmailMixin:
    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicates = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError("A user with this email already exists.")
        return email


# ---------------------------------------------------------------------------
# Authentication forms
# ---------------------------------------------------------------------------
class LoginForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "autocomplete": "username",
            "autofocus": True,
            "placeholder": "Username or email",
        })
        self.fields["password"].widget.attrs.update({"autocomplete": "current-password"})


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class StyledPasswordResetForm(StyledFormMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    pass


# ---------------------------------------------------------------------------
# User management forms
# ---------------------------------------------------------------------------
class UserCreateForm(StyledFormMixin, UniqueEmailMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "phone_number", "role")

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = role_choices_for(actor)
        self.fields["role"].initial = Role.VIEWER
        self.fields["email"].required = True
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        for name, autocomplete in (
            ("username", "username"),
            ("email", "email"),
            ("first_name", "given-name"),
            ("last_name", "family-name"),
            ("phone_number", "tel"),
            ("password1", "new-password"),
            ("password2", "new-password"),
        ):
            self.fields[name].widget.attrs["autocomplete"] = autocomplete


class UserUpdateForm(StyledFormMixin, UniqueEmailMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "profile_photo", "is_active")
        labels = {"is_active": "Account is active"}
        help_texts = {"is_active": "Inactive users cannot sign in."}
        widgets = {"profile_photo": forms.FileInput(attrs={"accept": "image/*"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True


class ProfileForm(StyledFormMixin, UniqueEmailMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "profile_photo")
        widgets = {"profile_photo": forms.FileInput(attrs={"accept": "image/*"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True


class RoleAssignForm(StyledFormMixin, forms.Form):
    role = forms.ChoiceField(label="New role")

    def __init__(self, *args, actor=None, current_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = role_choices_for(actor)
        self.fields["role"].initial = current_role


# ---------------------------------------------------------------------------
# Django admin forms (the stock ones point at auth.User)
# ---------------------------------------------------------------------------
class AdminSiteUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role")


class AdminSiteUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User