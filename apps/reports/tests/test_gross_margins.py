from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryTransaction
from apps.inventory.services import record_movement
from apps.members.models import Business, MemberProfile
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem
from apps.sales.services import complete_sale
from apps.commissions.models import SalesAgentCommission

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _setup_roles(roles):
    pass


def test_gross_margins_report_view_and_export(client, make_user):
    admin = make_user(role=Role.ADMIN)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="GM-1", name="Gross Margin Hub")
    HubMembership.objects.create(hub=hub, user=admin)
    HubMembership.objects.create(hub=hub, user=agent)

    product = Product.objects.create(
        sku="GM-PROD-1",
        name="Fertilizer",
        selling_price=Decimal("100.00"),
        cost_price=Decimal("60.00"),
    )

    record_movement(
        hub=hub,
        product=product,
        kind=InventoryTransaction.Kind.RECEIPT,
        quantity=10,
        actor=admin,
    )

    sale = complete_sale(
        hub=hub,
        agent=agent,
        actor=admin,
        items=[{"product": product.pk, "quantity": 2}],
        customer_name="Walk-in buyer",
    )

    client.force_login(admin)

    # HTML view
    response = client.get(reverse("reports:gross_margins"))
    assert response.status_code == 200
    assert b"Gross" in response.content
    assert b"Margins" in response.content
    assert b"Fertilizer" in response.content
    assert b"200.00" in response.content  # Revenue (2 * 100)
    assert b"120.00" in response.content  # Cost (2 * 60)
    assert b"80.00" in response.content   # Margin (200 - 120)

    # CSV export
    csv_response = client.get(reverse("reports:gross_margins") + "?format=csv")
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response["Content-Type"]
    assert b"Fertilizer" in csv_response.content

    # Excel export
    xlsx_response = client.get(reverse("reports:gross_margins") + "?format=xlsx")
    assert xlsx_response.status_code == 200
    assert "spreadsheetml" in xlsx_response["Content-Type"]


def test_sale_by_member_and_commission_accrual(make_user):
    admin = make_user(role=Role.ADMIN)
    member_user = make_user(role=Role.MEMBER, username="member_seller")
    hub = Hub.objects.create(code="GM-2", name="Member Seller Hub")
    HubMembership.objects.create(hub=hub, user=admin)
    HubMembership.objects.create(hub=hub, user=member_user)
    member_profile = MemberProfile.objects.create(user=member_user, hub=hub)

    product = Product.objects.create(
        sku="GM-PROD-2",
        name="Seed",
        selling_price=Decimal("50.00"),
        cost_price=Decimal("30.00"),
    )

    record_movement(
        hub=hub,
        product=product,
        kind=InventoryTransaction.Kind.RECEIPT,
        quantity=10,
        actor=admin,
    )

    sale = complete_sale(
        hub=hub,
        member=member_profile,
        actor=admin,
        items=[{"product": product.pk, "quantity": 4}],
        customer_name="Walk-in farmer",
    )

    assert sale.seller == member_user
    assert sale.seller_display == str(member_profile)
    assert sale.customer_type_display == "Walk-in"
    assert sale.customer_display == "Walk-in farmer"

    commission = SalesAgentCommission.objects.filter(sale=sale).first()
    assert commission is not None
    assert commission.agent == member_user
    assert commission.amount > 0
