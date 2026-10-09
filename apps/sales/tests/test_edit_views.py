import pytest
from django.urls import reverse

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db


def test_admin_can_start_new_sale_from_sales_list(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    client.force_login(admin)

    response = client.get(reverse("sales:list"))

    assert response.status_code == 200
    assert b"New sale" in response.content
    assert reverse("sales:create").encode() in response.content
    assert client.get(reverse("sales:create")).status_code == 200


def test_admin_can_edit_sale_customer_details_from_sales_list(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="SALE-EDIT", name="Sale edit hub")
    sale = Sale.objects.create(
        hub=hub,
        agent=agent,
        customer_name="Old customer",
        payment_reference="old-reference",
        total="125.00",
        status=Sale.Status.COMPLETED,
    )
    client.force_login(admin)

    sales_list = client.get(reverse("sales:list"))
    assert sales_list.status_code == 200
    assert reverse("sales:edit", args=[sale.pk]).encode() in sales_list.content

    edit_page = client.get(reverse("sales:edit", args=[sale.pk]))
    assert edit_page.status_code == 200
    assert b"Save changes" in edit_page.content
    assert b'name="total"' not in edit_page.content
    assert b'name="payment_method"' not in edit_page.content

    response = client.post(
        reverse("sales:edit", args=[sale.pk]),
        {
            "customer_name": "Updated customer",
            "customer_phone": "0712345678",
            "payment_reference": "new-reference",
            "notes": "Contact details corrected",
            "total": "1.00",
            "payment_method": Sale.PaymentMethod.CREDIT,
        },
    )

    assert response.status_code == 302
    sale.refresh_from_db()
    assert sale.customer_name == "Updated customer"
    assert sale.customer_phone == "0712345678"
    assert sale.payment_reference == "new-reference"
    assert sale.notes == "Contact details corrected"
    assert str(sale.total) == "125.00"
    assert sale.payment_method == Sale.PaymentMethod.CASH


def test_hub_manager_cannot_edit_sales_outside_their_hubs(client, make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    agent = make_user(role=Role.SALES_AGENT)
    assigned_hub = Hub.objects.create(code="SALE-MGR-OWN", name="Assigned")
    outside_hub = Hub.objects.create(code="SALE-MGR-OTHER", name="Not assigned")
    HubMembership.objects.create(hub=assigned_hub, user=manager)
    visible_sale = Sale.objects.create(hub=assigned_hub, agent=agent, customer_name="Visible")
    hidden_sale = Sale.objects.create(hub=outside_hub, agent=agent, customer_name="Hidden")
    client.force_login(manager)

    response = client.get(reverse("sales:list"))

    assert response.status_code == 200
    assert reverse("sales:edit", args=[visible_sale.pk]).encode() in response.content
    assert reverse("sales:edit", args=[hidden_sale.pk]).encode() not in response.content
    assert client.get(reverse("sales:edit", args=[hidden_sale.pk])).status_code == 404
