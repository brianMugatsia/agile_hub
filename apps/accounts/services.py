from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.audit.utils import AuditAction, log_action

from .permissions import can_manage_user
from .roles import ALL_PERMISSIONS, ROLE_PERMISSIONS, Role, assignable_roles


# ---------------------------------------------------------------------------
# Groups and permissions
# ---------------------------------------------------------------------------
def sync_user_group(user):
    """Keep the user in exactly one role group: the one matching `user.role`."""
    target, _ = Group.objects.get_or_create(name=user.role)
    stale = Group.objects.filter(name__in=Role.values).exclude(pk=target.pk)
    user.groups.remove(*stale)
    user.groups.add(target)


def sync_role_permissions():
    """Create one Group per role and attach its permissions. Safe to run repeatedly.

    Returns {role: {"assigned": int, "pending": [codenames whose models don't exist yet]}}.
    """
    summary = {}
    for role in Role.values:
        group, _ = Group.objects.get_or_create(name=role)
        codenames = ROLE_PERMISSIONS[role]
        if codenames is ALL_PERMISSIONS:
            permissions = Permission.objects.all()
            pending = []
        else:
            permissions = Permission.objects.filter(codename__in=codenames)
            pending = sorted(set(codenames) - set(permissions.values_list("codename", flat=True)))
        group.permissions.set(permissions)
        summary[role] = {"assigned": permissions.count(), "pending": pending}
    return summary


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
def _snapshot(user):
    return {
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "role": user.role,
        "is_active": user.is_active,
    }


def _jsonable(value):
    return value if isinstance(value, (str, int, float, bool, type(None))) else str(value)


@transaction.atomic
def create_user_from_form(form, *, actor, request=None):
    """Save a validated UserCreateForm and audit it. Enforces role-assignment rules again."""
    if form.cleaned_data["role"] not in assignable_roles(actor):
        raise PermissionDenied("You are not allowed to assign this role.")
    user = form.save()
    log_action(
        user=actor, action=AuditAction.USER_CREATED, model_name="User",
        object_id=user.pk, new_data=_snapshot(user), request=request,
    )
    return user


@transaction.atomic
def update_user_from_form(form, *, actor, request=None):
    """Save a validated UserUpdateForm and audit only the fields that changed."""
    if not can_manage_user(actor, form.instance):
        raise PermissionDenied("You cannot edit this user.")
    previous = {f: _jsonable(form.initial.get(f)) for f in form.changed_data if f != "profile_photo"}
    user = form.save()
    new = {f: _jsonable(form.cleaned_data.get(f)) for f in form.changed_data if f != "profile_photo"}
    if "profile_photo" in form.changed_data:
        new["profile_photo"] = "updated"
    if form.changed_data:
        log_action(
            user=actor, action=AuditAction.USER_UPDATED, model_name="User",
            object_id=user.pk, previous_data=previous, new_data=new, request=request,
        )
    return user


@transaction.atomic
def change_user_role(*, user, new_role, actor, request=None):
    """Change a user's role. The group and Django admin flags follow automatically."""
    if not can_manage_user(actor, user):
        raise PermissionDenied("You cannot change this user's role.")
    if new_role not in assignable_roles(actor):
        raise PermissionDenied("You are not allowed to assign this role.")
    if user.role == new_role:
        raise ValidationError("This user already has that role.")

    previous_role = user.role
    user.role = new_role
    user.save()
    log_action(
        user=actor, action=AuditAction.USER_ROLE_CHANGED, model_name="User",
        object_id=user.pk, previous_data={"role": previous_role},
        new_data={"role": new_role}, request=request,
    )
    return user