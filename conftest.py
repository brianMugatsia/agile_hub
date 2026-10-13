import itertools

import pytest

DEFAULT_PASSWORD = "StrongPass!234"


@pytest.fixture
def roles(db):
    """Create the role groups and attach permissions (mirrors the post_migrate hook)."""
    from apps.accounts.services import sync_role_permissions

    return sync_role_permissions()


@pytest.fixture
def make_user(db, roles):
    """Factory: make_user(role=Role.ADMIN, username="x") -> saved User."""
    from apps.accounts.models import User
    from apps.accounts.roles import Role
    from django.contrib.auth.models import Group

    counter = itertools.count(1)

    def _make(role=Role.VIEWER, password=DEFAULT_PASSWORD, **extra):
        n = next(counter)
        extra.setdefault("username", f"user{n}")
        extra.setdefault("email", f"user{n}@example.com")
        user = User.objects.create_user(password=password, role=role, **extra)
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
        return user

    return _make
