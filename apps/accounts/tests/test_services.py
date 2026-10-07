import logging

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.accounts import services
from apps.accounts.roles import Role

pytestmark = pytest.mark.django_db


def test_super_admin_can_change_role_and_it_is_audited(make_user, roles, caplog):
    caplog.set_level(logging.INFO, logger="audit")
    boss = make_user(role=Role.SUPER_ADMIN)
    target = make_user(role=Role.WORKER)

    services.change_user_role(user=target, new_role=Role.FINANCE_OFFICER, actor=boss)

    target.refresh_from_db()
    assert target.role == Role.FINANCE_OFFICER
    assert "USER_ROLE_CHANGED" in caplog.text


def test_admin_cannot_promote_to_super_admin(make_user, roles):
    admin = make_user(role=Role.ADMIN)
    target = make_user(role=Role.WORKER)
    with pytest.raises(PermissionDenied):
        services.change_user_role(user=target, new_role=Role.SUPER_ADMIN, actor=admin)


def test_nobody_can_change_their_own_role(make_user, roles):
    boss = make_user(role=Role.SUPER_ADMIN)
    with pytest.raises(PermissionDenied):
        services.change_user_role(user=boss, new_role=Role.VIEWER, actor=boss)


def test_admin_cannot_touch_another_admin(make_user, roles):
    admin = make_user(role=Role.ADMIN)
    other = make_user(role=Role.ADMIN)
    with pytest.raises(PermissionDenied):
        services.change_user_role(user=other, new_role=Role.VIEWER, actor=admin)


def test_setting_the_same_role_is_rejected(make_user, roles):
    boss = make_user(role=Role.SUPER_ADMIN)
    target = make_user(role=Role.WORKER)
    with pytest.raises(ValidationError):
        services.change_user_role(user=target, new_role=Role.WORKER, actor=boss)