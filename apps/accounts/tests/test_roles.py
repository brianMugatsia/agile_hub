import pytest
from django.contrib.auth.models import Group, Permission

from apps.accounts.roles import ROLE_PERMISSIONS, Role, assignable_roles

pytestmark = pytest.mark.django_db


def test_user_is_placed_in_matching_role_group(make_user, roles):
    user = make_user(role=Role.WORKER)
    assert list(user.groups.values_list("name", flat=True)) == [Role.WORKER]


def test_changing_role_moves_user_between_groups(make_user, roles):
    user = make_user(role=Role.WORKER)
    user.role = Role.VIEWER
    user.save()
    assert list(user.groups.values_list("name", flat=True)) == [Role.VIEWER]


def test_admin_group_gets_expected_permissions(roles):
    codenames = set(Group.objects.get(name=Role.ADMIN).permissions.values_list("codename", flat=True))
    assert {"view_user", "add_user", "change_user", "assign_roles"} <= codenames
    assert "delete_user" not in codenames


def test_viewer_cannot_manage_users(make_user, roles):
    viewer = make_user(role=Role.VIEWER)
    assert not viewer.has_perm("accounts.view_user")
    assert not viewer.has_perm("accounts.add_user")


def test_admin_user_has_permission_through_group(make_user, roles):
    admin = make_user(role=Role.ADMIN)
    assert admin.has_perm("accounts.view_user")


def test_super_admin_group_holds_every_permission(roles):
    group = Group.objects.get(name=Role.SUPER_ADMIN)
    assert group.permissions.count() == Permission.objects.count()


def test_admin_cannot_assign_admin_or_super_admin(make_user):
    admin = make_user(role=Role.ADMIN)
    allowed = assignable_roles(admin)
    assert Role.SUPER_ADMIN not in allowed and Role.ADMIN not in allowed
    assert Role.SALES_AGENT in allowed


def test_non_managers_assign_no_roles(make_user):
    assert assignable_roles(make_user(role=Role.HUB_MANAGER)) == ()


def test_salary_and_commission_permissions_are_kept_apart():
    """Salaries and commissions must never be granted through one another."""
    assert "view_salesagentcommission" not in ROLE_PERMISSIONS[Role.WORKER]
    assert "view_salaryrecord" not in ROLE_PERMISSIONS[Role.SALES_AGENT]
    assert "pay_salaryrecord" not in ROLE_PERMISSIONS[Role.ADMIN]