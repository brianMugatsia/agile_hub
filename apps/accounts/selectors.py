from django.db.models import Q
from .models import User
from .roles import Role


def users_visible_to(actor):
    """Users the actor may see. Hub managers see users in their hubs."""
    role = getattr(actor, "role", None)
    queryset = User.objects.all()
    if role == Role.SUPER_ADMIN:
        return queryset
    if role == Role.ADMIN:
        return queryset.exclude(role=Role.SUPER_ADMIN)
    if role == Role.HUB_MANAGER:
        hub_ids = list(actor.hub_memberships.filter(is_active=True).values_list("hub_id", flat=True))
        if actor.hub_id and actor.hub_id not in hub_ids:
            hub_ids.append(actor.hub_id)
        if not hub_ids:
            return queryset.filter(pk=actor.pk)
        return queryset.filter(Q(hub_id__in=hub_ids) | Q(hub_memberships__hub_id__in=hub_ids)).distinct()
    return queryset.none()
