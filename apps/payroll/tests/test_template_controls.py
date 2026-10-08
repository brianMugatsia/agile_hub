import pytest

from django.urls import reverse

from apps.accounts.roles import Role

pytestmark = pytest.mark.django_db


def test_salary_list_renders_one_pair_of_export_buttons(client, make_user):
    admin = make_user(role=Role.ADMIN, is_superuser=True)
    client.force_login(admin)

    response = client.get(reverse("payroll:salary_list"))

    assert response.status_code == 200
    assert response.content.count(b"Download CSV") == 1
    assert response.content.count(b"Download Excel") == 1
