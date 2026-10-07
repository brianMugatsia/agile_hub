import itertools

import pytest

DEFAULT_PASSWORD = "StrongPass!234"


@pytest.fixture
def roles(db):
    """Create the role groups and attach permissions (mirrors the post_migrate hook)."""
    from apps.accounts.services import sync_role_permissions

    return sync_role_permissions()


@pytest.fixture
def make_user(db):
    """Factory: make_user(role=Role.ADMIN, username="x") -> saved User."""
    from apps.accounts.models import User
    from apps.accounts.roles import Role

    counter = itertools.count(1)

    def _make(role=Role.VIEWER, password=DEFAULT_PASSWORD, **extra):
        n = next(counter)
        extra.setdefault("username", f"user{n}")
        extra.setdefault("email", f"user{n}@example.com")
        return User.objects.create_user(password=password, role=role, **extra)

    return _make