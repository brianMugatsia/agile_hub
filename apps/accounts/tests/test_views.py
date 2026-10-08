import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role

pytestmark = pytest.mark.django_db

PASSWORD = "StrongPass!234"


def test_login_redirects_to_dashboard(client, make_user):
    make_user(username="jane")
    response = client.post(reverse("accounts:login"), {"username": "jane", "password": PASSWORD})
    assert response.status_code == 302
    assert response.url == reverse("core:dashboard")


def test_wrong_password_shows_error(client, make_user):
    make_user(username="jane")
    response = client.post(reverse("accounts:login"), {"username": "jane", "password": "wrong"})
    assert response.status_code == 200
    assert response.context["form"].errors


def test_login_form_uses_styled_accessible_controls(client):
    response = client.get(reverse("accounts:login"))

    assert response.status_code == 200
    assert b'class="input"' in response.content
    assert b'placeholder="Username or email"' in response.content
    assert b'autocomplete="current-password"' in response.content


def test_user_registration_fields_include_styling_and_autocomplete(client, make_user, roles):
    client.force_login(make_user(role=Role.SUPER_ADMIN))
    response = client.get(reverse("accounts:user_create"))

    assert response.status_code == 200
    assert b'autocomplete="given-name"' in response.content
    assert b'autocomplete="new-password"' in response.content
    assert b'class="input"' in response.content


def test_user_search_filter_keeps_query_and_modern_filter_controls(client, make_user, roles):
    client.force_login(make_user(role=Role.ADMIN))
    response = client.get(reverse("accounts:user_list"), {"q": "worker"})

    assert response.status_code == 200
    assert b'aria-label="Filter users"' in response.content
    assert b'type="search"' in response.content
    assert b'value="worker"' in response.content


def test_dashboard_requires_login(client):
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 302
    assert response.url == f"{reverse('accounts:login')}?next={reverse('core:dashboard')}"


@pytest.mark.parametrize("role", Role.values)
def test_each_role_gets_its_own_dashboard(client, make_user, role):
    client.force_login(make_user(role=role))
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 200
    assert f"dashboard/{role.lower()}.html" in [t.name for t in response.templates]


def test_logout_requires_post(client, make_user):
    client.force_login(make_user())
    assert client.get(reverse("accounts:logout")).status_code == 405
    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert response.url == reverse("core:home")
    home = client.get(response.url)
    assert home.status_code == 200
    assert b"About" in home.content


def test_user_can_update_own_profile(client, make_user):
    user = make_user(role=Role.WORKER)
    client.force_login(user)
    response = client.post(reverse("accounts:profile"), {
        "first_name": "Ann", "last_name": "Wanjiru",
        "email": user.email, "phone_number": "+254712345678",
    })
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.phone_number == "+254712345678"


def test_viewer_gets_403_on_user_list(client, make_user, roles):
    client.force_login(make_user(role=Role.VIEWER))
    assert client.get(reverse("accounts:user_list")).status_code == 403


def test_admin_list_hides_super_admins(client, make_user, roles):
    client.force_login(make_user(role=Role.ADMIN))
    make_user(role=Role.SUPER_ADMIN, username="boss")
    make_user(role=Role.SALES_AGENT, username="agent1")

    response = client.get(reverse("accounts:user_list"))
    usernames = [u.username for u in response.context["users"]]
    assert "agent1" in usernames
    assert "boss" not in usernames


def test_admin_cannot_open_super_admin_by_id(client, make_user, roles):
    client.force_login(make_user(role=Role.ADMIN))
    boss = make_user(role=Role.SUPER_ADMIN)
    assert client.get(reverse("accounts:user_detail", args=[boss.pk])).status_code == 404


def test_admin_cannot_edit_another_admin(client, make_user, roles):
    client.force_login(make_user(role=Role.ADMIN))
    other = make_user(role=Role.ADMIN)
    assert client.get(reverse("accounts:user_edit", args=[other.pk])).status_code == 403


def test_super_admin_can_create_user(client, make_user, roles):
    client.force_login(make_user(role=Role.SUPER_ADMIN))
    response = client.post(reverse("accounts:user_create"), {
        "username": "newagent", "email": "agent@example.com",
        "first_name": "Ann", "last_name": "Wanjiru", "phone_number": "+254712345678",
        "role": Role.SALES_AGENT, "password1": PASSWORD, "password2": PASSWORD,
    })
    assert response.status_code == 302
    created = User.objects.get(username="newagent")
    assert created.role == Role.SALES_AGENT
    assert created.groups.filter(name=Role.SALES_AGENT).exists()


def test_admin_cannot_create_super_admin(client, make_user, roles):
    client.force_login(make_user(role=Role.ADMIN))
    response = client.post(reverse("accounts:user_create"), {
        "username": "sneaky", "email": "sneaky@example.com",
        "first_name": "S", "last_name": "N", "phone_number": "",
        "role": Role.SUPER_ADMIN, "password1": PASSWORD, "password2": PASSWORD,
    })
    assert response.status_code == 200
    assert not User.objects.filter(username="sneaky").exists()


def test_super_admin_can_change_role_through_the_page(client, make_user, roles):
    client.force_login(make_user(role=Role.SUPER_ADMIN))
    target = make_user(role=Role.WORKER)
    response = client.post(reverse("accounts:user_role", args=[target.pk]), {"role": Role.FINANCE_OFFICER})
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.role == Role.FINANCE_OFFICER


def test_admin_cannot_grant_super_admin_through_the_page(client, make_user, roles):
    client.force_login(make_user(role=Role.ADMIN))
    target = make_user(role=Role.WORKER)
    response = client.post(reverse("accounts:user_role", args=[target.pk]), {"role": Role.SUPER_ADMIN})
    assert response.status_code == 200
    target.refresh_from_db()
    assert target.role == Role.WORKER