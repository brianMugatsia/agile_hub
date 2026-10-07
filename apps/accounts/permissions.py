from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from rest_framework.permissions import DjangoModelPermissions

from .roles import Role


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a class-based view to the roles in `allowed_roles`."""

    allowed_roles = ()

    def test_func(self):
        return self.request.user.role in self.allowed_roles


def can_manage_user(actor, target):
    """Whether `actor` may edit `target` or change their role. Nobody manages themselves here."""
    if not getattr(actor, "is_authenticated", False) or actor.pk == target.pk:
        return False
    if actor.role == Role.SUPER_ADMIN:
        return True
    if actor.role == Role.ADMIN:
        return target.role not in (Role.SUPER_ADMIN, Role.ADMIN)
    return False


class DjangoViewPermission(DjangoModelPermissions):
    """Like DjangoModelPermissions, but reading also requires the `view_` permission."""

    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
    }