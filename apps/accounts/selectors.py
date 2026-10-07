from .models import User
from .roles import Role


def users_visible_to(actor):
    """Users the actor may see. Hub scoping for ADMIN is added in Stage 2."""
    role = getattr(actor, "role", None)
    queryset = User.objects.all()
    if role == Role.SUPER_ADMIN:
        return queryset
    if role == Role.ADMIN:
        return queryset.exclude(role=Role.SUPER_ADMIN)
    return queryset.none()