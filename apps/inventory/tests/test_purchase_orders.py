from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import (
    InventoryBalance,
    InventoryTransaction,
    PurchaseOrder,
    Supplier,
)
from apps.inventory.services import create_reorder_order, receive_purchase_order
from apps.products.models import Product

pytestmark = pytest.mark.django_db


def test_reorder_order_uses_only_low_stock_products_and_receiving_posts_ledger(make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    hub = Hub.objects.create(code="PO-HUB", name="Purchase Hub", manager=manager)
    supplier = Supplier.objects.create(code="SUP-1", name="Main Supplier")
    low_stock = Product.objects.create(
        sku="PO-LOW",
        name="Low item",
        cost_price=Decimal("4.50"),
        selling_price=Decimal("7.00"),
        reorder_level=5,
    )
    healthy = Product.objects.create(
        sku="PO-OK",
        name="Healthy item",
        selling_price=Decimal("7.00"),
        reorder_level=5,
    )
    never_stocked = Product.objects.create(
        sku="PO-NEW",
        name="Never stocked",
        cost_price=Decimal("2.00"),
        selling_price=Decimal("4.00"),
        reorder_level=4,
    )
    InventoryBalance.objects.create(hub=hub, product=low_stock, quantity=2)
    InventoryBalance.objects.create(hub=hub, product=healthy, quantity=6)

    order = create_reorder_order(hub=hub, supplier=supplier, actor=manager)
    line = order.lines.get(product=low_stock)
    never_stocked_line = order.lines.get(product=never_stocked)

    assert line.product == low_stock
    assert line.quantity_ordered == 8
    assert line.unit_cost == Decimal("4.50")
    assert never_stocked_line.quantity_ordered == 8
    assert order.status == PurchaseOrder.Status.ORDERED

    def quantities_for(selected_quantity):
        return {
            item.pk: selected_quantity if item.pk == line.pk else 0
            for item in order.lines.all()
        }

    partial = receive_purchase_order(
        order_id=order.pk,
        quantities=quantities_for(3),
        actor=manager,
    )
    line.refresh_from_db()
    assert partial.status == PurchaseOrder.Status.PARTIALLY_RECEIVED
    assert line.quantity_received == 3
    assert InventoryBalance.objects.get(hub=hub, product=low_stock).quantity == 5
    assert InventoryTransaction.objects.filter(
        hub=hub,
        product=low_stock,
        kind=InventoryTransaction.Kind.RECEIPT,
        reference=f"PO-{order.pk}",
        quantity=3,
    ).exists()

    complete = receive_purchase_order(
        order_id=order.pk,
        quantities={
            line.pk: 5,
            never_stocked_line.pk: never_stocked_line.quantity_ordered,
        },
        actor=manager,
    )
    line.refresh_from_db()
    assert complete.status == PurchaseOrder.Status.RECEIVED
    assert line.quantity_received == line.quantity_ordered
    assert InventoryBalance.objects.get(hub=hub, product=low_stock).quantity == 10


def test_reorder_order_requires_low_stock_and_user_hub_access(make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    other_manager = make_user(role=Role.HUB_MANAGER)
    hub = Hub.objects.create(code="PO-SCOPE", name="Scoped Hub", manager=manager)
    supplier = Supplier.objects.create(code="SUP-2", name="Scoped Supplier")
    product = Product.objects.create(
        sku="PO-SCOPE-P",
        name="Product",
        selling_price=Decimal("5.00"),
        reorder_level=2,
    )
    InventoryBalance.objects.create(hub=hub, product=product, quantity=2)

    with pytest.raises(PermissionDenied):
        create_reorder_order(hub=hub, supplier=supplier, actor=other_manager)

    order = create_reorder_order(hub=hub, supplier=supplier, actor=manager)
    line = order.lines.get()
    with pytest.raises(ValidationError):
        receive_purchase_order(
            order_id=order.pk,
            quantities={line.pk: line.quantity_ordered + 1},
            actor=manager,
        )
    line.refresh_from_db()
    assert line.quantity_received == 0
    assert not InventoryTransaction.objects.filter(reference=f"PO-{order.pk}").exists()
    assert HubMembership.objects.filter(hub=hub).count() == 0


def test_reorder_creation_rejects_when_nothing_needs_reordering(make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    hub = Hub.objects.create(code="PO-CLEAR", name="Healthy Hub", manager=manager)
    supplier = Supplier.objects.create(code="SUP-3", name="Supplier")
    product = Product.objects.create(
        sku="PO-CLEAR-P",
        name="Healthy item",
        selling_price=Decimal("5.00"),
        reorder_level=2,
    )
    InventoryBalance.objects.create(hub=hub, product=product, quantity=4)

    with pytest.raises(ValidationError, match="no active products"):
        create_reorder_order(hub=hub, supplier=supplier, actor=manager)

    assert not PurchaseOrder.objects.exists()


def test_purchase_order_views_create_and_receive_using_scoped_hub(client, make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    outsider = make_user(role=Role.HUB_MANAGER)
    hub = Hub.objects.create(code="PO-VIEW", name="View Hub", manager=manager)
    supplier = Supplier.objects.create(code="SUP-VIEW", name="View Supplier")
    product = Product.objects.create(
        sku="PO-VIEW-P",
        name="View product",
        selling_price=Decimal("6.00"),
        reorder_level=2,
    )
    client.force_login(manager)

    assert client.get(reverse("inventory:purchase_order_create")).status_code == 200
    assert client.get(reverse("inventory:suppliers")).status_code == 200
    created = client.post(
        reverse("inventory:purchase_order_create"),
        {"hub": str(hub.pk), "supplier": supplier.pk, "notes": "Weekly restock"},
    )
    order = PurchaseOrder.objects.get()
    line = order.lines.get(product=product)

    assert created.status_code == 302
    assert order.notes == "Weekly restock"
    client.force_login(outsider)
    assert client.get(
        reverse("inventory:purchase_order_receive", args=[order.pk])
    ).status_code == 404

    client.force_login(manager)
    received = client.post(
        reverse("inventory:purchase_order_receive", args=[order.pk]),
        {f"line_{line.pk}": line.quantity_ordered},
    )

    order.refresh_from_db()
    assert received.status_code == 302
    assert order.status == PurchaseOrder.Status.RECEIVED
    assert InventoryBalance.objects.get(hub=hub, product=product).quantity == 4
