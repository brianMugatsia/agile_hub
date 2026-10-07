from django.db.models import Q

from apps.accounts.roles import Role
from .models import Hub


def hubs_for_user(user, *, active_only=False):
    queryset = Hub.objects.all()
    if active_only:
        queryset = queryset.filter(status=Hub.Status.ACTIVE)
    if getattr(user, "role", None) in (Role.SUPER_ADMIN, Role.ADMIN):
        return queryset
    return queryset.filter(
        Q(manager=user) | Q(memberships__user=user, memberships__is_active=True)
    ).distinct()


def user_can_access_hub(user, hub):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "role", None) in (Role.SUPER_ADMIN, Role.ADMIN):
        return True
    return hub.manager_id == user.pk or hub.memberships.filter(user=user, is_active=True).exists()