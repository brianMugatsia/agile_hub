import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.roles import Role

pytestmark = pytest.mark.django_db

PASSWORD = "StrongPass!234"


def test_me_requires_authentication():
    assert APIClient().get(reverse("accounts_api:me")).status_code == 401


def test_jwt_login_then_me(make_user):
    make_user(username="apiuser", role=Role.WORKER)
    client = APIClient()
    token = client.post(
        reverse("token_obtain_pair"), {"username": "apiuser", "password": PASSWORD}, format="json"
    )
    assert token.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
    me = client.get(reverse("accounts_api:me"))
    assert me.status_code == 200
    assert me.data["username"] == "apiuser"
    assert me.data["role"] == Role.WORKER


def test_viewer_cannot_list_users(make_user, roles):
    client = APIClient()
    client.force_authenticate(make_user(role=Role.VIEWER))
    assert client.get(reverse("accounts_api:user-list")).status_code == 403


def test_admin_user_list_excludes_super_admins(make_user, roles):
    make_user(role=Role.SUPER_ADMIN, username="boss")
    make_user(role=Role.WORKER, username="worker1")
    client = APIClient()
    client.force_authenticate(make_user(role=Role.ADMIN))

    response = client.get(reverse("accounts_api:user-list"))
    assert response.status_code == 200
    usernames = [row["username"] for row in response.data["results"]]
    assert "worker1" in usernames
    assert "boss" not in usernames