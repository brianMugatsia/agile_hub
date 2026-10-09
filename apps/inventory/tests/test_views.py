from apps.accounts.roles import Role
from apps.inventory.models import Supplier
from django.urls import reverse

import pytest

pytestmark = pytest.mark.django_db


def test_admin_can_edit_supplier_and_view_inactive_suppliers(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    supplier = Supplier.objects.create(
        code="SUP-EDIT",
        name="Old supplier name",
        is_active=False,
    )
    client.force_login(admin)

    list_url = reverse("inventory:suppliers")
    edit_url = reverse("inventory:supplier_edit", args=[supplier.pk])
    list_response = client.get(list_url)

    assert list_response.status_code == 200
    assert b"Inactive" in list_response.content
    assert edit_url.encode() in list_response.content
    response = client.post(
        edit_url,
        {
            "code": supplier.code,
            "name": "Updated supplier",
            "contact_name": "Sam",
            "email": "sam@example.com",
            "phone": "0712345678",
            "address": "Market road",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    supplier.refresh_from_db()
    assert supplier.name == "Updated supplier"
    assert supplier.is_active