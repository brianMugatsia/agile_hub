import pytest
from decimal import Decimal
from django.urls import reverse

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.inventory.services import record_movement
from apps.products.models import Product
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


def test_sales_agent_can_create_sale(client, make_user, roles):
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="AGENT-HUB", name="Agent Hub")
    HubMembership.objects.create(hub=hub, user=agent)
    product = Product.objects.create(
        sku="SKU-AGT",
        name="Agent product",
        cost_price=Decimal("4.00"),
        selling_price=Decimal("10.00"),
        stock_on_hand=0,
    )
    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=10, actor=agent)
    client.force_login(agent)
    response = client.post(
        reverse("sales:create"),
        {
            "hub": hub.pk,
            "seller_type": "agent",
            "agent": agent.pk,
            "product": product.pk,
            "quantity": 2,
            "payment_method": Sale.PaymentMethod.CASH,
            "customer_name": "Walk-in",
        },
    )
    assert response.status_code == 302
    sale = Sale.objects.get(hub=hub)
    assert sale.agent == agent
    assert sale.total == Decimal("20.00")


def test_sales_agent_cannot_create_sale_for_another_agent(client, make_user, roles):
    agent1 = make_user(role=Role.SALES_AGENT, username="agent1")
    agent2 = make_user(role=Role.SALES_AGENT, username="agent2")
    hub = Hub.objects.create(code="AGENT-HUB-2", name="Agent Hub 2")
    HubMembership.objects.create(hub=hub, user=agent1)
    HubMembership.objects.create(hub=hub, user=agent2)
    product = Product.objects.create(
        sku="SKU-AGT2",
        name="Agent product 2",
        cost_price=Decimal("4.00"),
        selling_price=Decimal("10.00"),
        stock_on_hand=0,
    )
    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=10, actor=agent1)
    client.force_login(agent1)
    response = client.post(
        reverse("sales:create"),
        {
            "hub": hub.pk,
            "seller_type": "agent",
            "agent": agent2.pk,
            "product": product.pk,
            "quantity": 1,
            "payment_method": Sale.PaymentMethod.CASH,
            "customer_name": "Walk-in",
        },
    )
    assert response.status_code == 200
    assert "agent" in response.context["form"].errors


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
