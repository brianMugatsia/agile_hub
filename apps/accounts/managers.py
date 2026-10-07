from django.contrib.auth.models import UserManager as DjangoUserManager

from .roles import Role


class UserManager(DjangoUserManager):
    """Creates users with a role. Superusers are always SUPER_ADMIN."""

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.VIEWER)
        return super().create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["role"] = Role.SUPER_ADMIN
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return super().create_superuser(username, email, password, **extra_fields)