from django.db.models import Q

from apps.accounts.roles import Role
from .models import Hub

PLATFORM_ROLES = (Role.SUPER_ADMIN, Role.ADMIN)


def hubs_for_user(user, *, active_only=False):
    queryset = Hub.objects.all()
    if active_only:
        queryset = queryset.filter(status=Hub.Status.ACTIVE)
    if getattr(user, "role", None) in PLATFORM_ROLES:
        return queryset
    if getattr(user, "role", None) == Role.BENEFICIARY:
        return queryset.filter(
            Q(beneficiaries__user=user) | Q(businesses__beneficiary__user=user)
        ).distinct()
    if getattr(user, "role", None) == Role.WORKER:
        return queryset.filter(workers__user=user).distinct()
    return queryset.filter(
        Q(manager=user) | Q(memberships__user=user, memberships__is_active=True)
    ).distinct()


def user_can_access_hub(user, hub):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "role", None) in PLATFORM_ROLES:
        return True
    if getattr(user, "role", None) == Role.BENEFICIARY:
        return (
            hub.beneficiaries.filter(user=user).exists()
            or hub.businesses.filter(beneficiary__user=user).exists()
        )
    if getattr(user, "role", None) == Role.WORKER:
        return hub.workers.filter(user=user).exists()
    return hub.manager_id == user.pk or hub.memberships.filter(user=user, is_active=True).exists()


def hub_is_locked(user, hubs):
    """Users who are not platform admins and belong to exactly one hub always work inside it."""
    if getattr(user, "role", None) in PLATFORM_ROLES:
        return False
    return len(hubs) == 1


def selected_hub(request, user=None):
    """Return accessible hubs, selected hub, and validation error for a hub filter.

    The result is computed once per request and reused by the sidebar, the top bar and the view.
    """
    user = user or request.user
    cached = getattr(request, "_selected_hub_result", None)
    if cached is not None and cached[0] == user.pk:
        return cached[1]
    result = _resolve_selected_hub(request, user)
    request._selected_hub_result = (user.pk, result)
    return result


def _resolve_selected_hub(request, user):
    hubs = hubs_for_user(user)

    if hub_is_locked(user, hubs):
        only_hub = hubs[0]
        if request.session.get("active_hub_id") != str(only_hub.pk):
            request.session["active_hub_id"] = str(only_hub.pk)
        return hubs, only_hub, ""

    if "hub" in request.GET:
        hub_id = request.GET.get("hub", "").strip()
        if not hub_id:
            request.session.pop("active_hub_id", None)
        else:
            hub = hubs.filter(pk=hub_id).first()
            if hub is None:
                return hubs, None, "Choose a hub you can access."
            request.session["active_hub_id"] = str(hub.pk)
            return hubs, hub, ""
    else:
        hub_id = request.session.get("active_hub_id", "")
    if not hub_id:
        return hubs, None, ""
    hub = hubs.filter(pk=hub_id).first()
    if hub is None:
        request.session.pop("active_hub_id", None)
        return hubs, None, "Choose a hub you can access."
    return hubs, hub, ""