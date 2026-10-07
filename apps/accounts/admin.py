from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.audit.utils import AuditAction, log_action

from .forms import AdminSiteUserChangeForm, AdminSiteUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = AdminSiteUserChangeForm
    add_form = AdminSiteUserCreationForm

    list_display = ("username", "email", "get_full_name", "role", "is_active", "last_login")
    list_filter = ("role", "is_active")
    search_fields = ("username", "email", "first_name", "last_name", "phone_number")
    ordering = ("username",)
    filter_horizontal = ()  # groups follow the role automatically

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "phone_number", "profile_photo")}),
        ("Role and access", {"fields": ("role", "is_active")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "first_name", "last_name", "role", "password1", "password2"),
        }),
    )
    readonly_fields = ("last_login", "date_joined")

    def save_model(self, request, obj, form, change):
        previous_role = User.objects.get(pk=obj.pk).role if change else None
        super().save_model(request, obj, form, change)
        if not change:
            log_action(
                user=request.user, action=AuditAction.USER_CREATED, model_name="User",
                object_id=obj.pk, new_data={"username": obj.username, "role": obj.role}, request=request,
            )
        elif "role" in form.changed_data:
            log_action(
                user=request.user, action=AuditAction.USER_ROLE_CHANGED, model_name="User",
                object_id=obj.pk, previous_data={"role": previous_role},
                new_data={"role": obj.role}, request=request,
            )