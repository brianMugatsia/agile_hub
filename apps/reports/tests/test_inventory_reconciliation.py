from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryTransaction
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem

pytestmark = pytest.mark.django_db


def _sale(*, hub, agent, product, quantity, status=Sale.Status.COMPLETED):
    sale = Sale.objects.create(
        hub=hub,
        agent=agent,
        status=status,
        completed_at=timezone.now(),
        total=Decimal("30.00"),
    )
    SaleItem.objects.create(
        sale=sale,
        product=product,
        quantity=quantity,
        unit_price=Decimal("10.00"),
        unit_cost=Decimal("5.00"),
    )
    return sale


def test_reconciliation_flags_missing_sale_movement_and_clears_after_matching_ledger(
    client, make_user, roles
):
    manager = make_user(role=Role.HUB_MANAGER)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="REC-1", name="Reconcile Hub", manager=manager)
    product = Product.objects.create(
        sku="REC-P",
        name="Reconcile item",
        selling_price=Decimal("10.00"),
    )
    sale = _sale(hub=hub, agent=agent, product=product, quantity=3)
    client.force_login(manager)

    mismatch = client.get(reverse("reports:inventory_reconciliation"))
    assert mismatch.status_code == 200
    assert b"Reconcile item" in mismatch.content
    assert b">3</td>" in mismatch.content
    assert b">0</td>" in mismatch.content
    assert b"Missing stock movement" in mismatch.content
    assert mismatch.context["check_count"] == 1
    assert mismatch.context["matched_count"] == 0
    assert b"recon-stats" in mismatch.content

    InventoryTransaction.objects.create(
        hub=hub,
        product=product,
        kind=InventoryTransaction.Kind.SALE,
        direction=InventoryTransaction.Direction.OUT,
        quantity=3,
        reference=str(sale.pk),
    )
    matched = client.get(reverse("reports:inventory_reconciliation"))
    assert matched.status_code == 200
    assert b"Everything reconciles" in matched.content
    assert matched.context["check_count"] == 1
    assert matched.context["matched_count"] == 1


def test_reconciliation_reports_unmatched_stock_movements_without_broken_sale_links(
    client, make_user, roles
):
    admin = make_user(role=Role.ADMIN)
    hub = Hub.objects.create(code="REC-ORPHAN", name="Orphan movement hub")
    product = Product.objects.create(
        sku="REC-ORPHAN-P", name="Orphan product", selling_price=Decimal("10.00")
    )
    orphan_reference = "orphan-sale-reference"
    InventoryTransaction.objects.create(
        hub=hub,
        product=product,
        kind=InventoryTransaction.Kind.SALE,
        direction=InventoryTransaction.Direction.OUT,
        quantity=2,
        reference=orphan_reference,
    )
    client.force_login(admin)

    response = client.get(reverse("reports:inventory_reconciliation"))

    assert response.status_code == 200
    assert b"Unmatched stock movement" in response.content
    assert b"orphan-sale" in response.content
    assert b'href="/sales/orphan-sale-reference/"' not in response.content
    assert response.context["check_count"] == 1
    assert response.context["matched_count"] == 0


def test_reconciliation_is_scoped_to_user_hubs_and_rejects_long_ranges(
    client, make_user, roles
):
    manager = make_user(role=Role.HUB_MANAGER)
    agent = make_user(role=Role.SALES_AGENT)
    accessible = Hub.objects.create(code="REC-2", name="Accessible Hub", manager=manager)
    other = Hub.objects.create(code="REC-3", name="Other Hub")
    product = Product.objects.create(
        sku="REC-S",
        name="Scoped item",
        selling_price=Decimal("10.00"),
    )
    _sale(hub=accessible, agent=agent, product=product, quantity=1)
    _sale(hub=other, agent=agent, product=product, quantity=2)
    HubMembership.objects.create(hub=accessible, user=manager)
    client.force_login(manager)

    scoped = client.get(reverse("reports:inventory_reconciliation"))
    too_long = client.get(
        reverse("reports:inventory_reconciliation"),
        {"start": "2025-01-01", "end": "2026-10-08"},
    )

    assert scoped.status_code == 200
    assert b"Accessible Hub" in scoped.content
    assert b"Other Hub" not in scoped.content
    assert b"no more than 366 days" in too_long.content
