from .models import User
from .roles import Role


def users_visible_to(actor):
    """Users the actor may see. Hub managers see users in their hub."""
    role = getattr(actor, "role", None)
    queryset = User.objects.all()
    if role == Role.SUPER_ADMIN:
        return queryset
    if role == Role.ADMIN:
        return queryset.exclude(role=Role.SUPER_ADMIN)
    if role == Role.HUB_MANAGER:
        user_hub = getattr(actor, "hub", None)
        if user_hub is not None:
            return queryset.filter(hub=user_hub)
        hub_ids = actor.hub_memberships.filter(is_active=True).values_list("hub_id", flat=True)
        return queryset.filter(hub_id__in=hub_ids)
    return queryset.none()
