from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryBalance
from apps.inventory.services import record_movement
from apps.notifications.models import Notification
from apps.products.models import Product

pytestmark = pytest.mark.django_db


def _hub(code, *, manager=None):
    return Hub.objects.create(code=code, name=f"Hub {code}", manager=manager)


def _product():
    return Product.objects.create(
        sku="LOW-STOCK-001",
        name="Seed pack",
        cost_price=Decimal("4.00"),
        selling_price=Decimal("10.00"),
        reorder_level=3,
        stock_on_hand=0,
    )


def test_alerts_on_threshold_crossing_and_only_after_recovery(make_user):
    manager = make_user(role=Role.HUB_MANAGER)
    active_manager = make_user(role=Role.HUB_MANAGER)
    inactive_manager = make_user(role=Role.HUB_MANAGER)
    other_role_member = make_user(role=Role.SALES_AGENT)
    unrelated_manager = make_user(role=Role.HUB_MANAGER)
    hub = _hub("LOW-001", manager=manager)
    other_hub = _hub("LOW-002")
    HubMembership.objects.create(hub=hub, user=active_manager, is_active=True)
    HubMembership.objects.create(hub=hub, user=inactive_manager, is_active=False)
    HubMembership.objects.create(hub=hub, user=other_role_member, is_active=True)
    HubMembership.objects.create(hub=other_hub, user=unrelated_manager, is_active=True)
    product = _product()

    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=5)
    assert not Notification.objects.exists()

    record_movement(hub=hub, product=product, kind="ISSUE", quantity=2)
    assert Notification.objects.filter(title="Low stock alert").count() == 2
    assert set(
        Notification.objects.values_list("recipient_id", flat=True)
    ) == {manager.pk, active_manager.pk}
    assert all(
        notification.target_url == "/inventory/"
        and "3 remaining" in notification.message
        for notification in Notification.objects.all()
    )

    record_movement(hub=hub, product=product, kind="ISSUE", quantity=1)
    assert Notification.objects.filter(title="Low stock alert").count() == 2
    assert InventoryBalance.objects.get(hub=hub, product=product).quantity == 2

    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=2)
    assert Notification.objects.filter(title="Low stock alert").count() == 2
    record_movement(hub=hub, product=product, kind="ISSUE", quantity=1)
    assert Notification.objects.filter(title="Low stock alert").count() == 4


def test_low_stock_notification_rolls_back_with_movement(make_user):
    manager = make_user(role=Role.HUB_MANAGER)
    hub = _hub("LOW-003", manager=manager)
    product = _product()
    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=5)

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            record_movement(hub=hub, product=product, kind="ISSUE", quantity=2)
            raise RuntimeError("roll back movement")

    assert not Notification.objects.exists()
    assert InventoryBalance.objects.get(hub=hub, product=product).quantity == 5


def test_only_hub_access_allows_actor_to_trigger_movement_and_alert(make_user):
    manager = make_user(role=Role.HUB_MANAGER)
    inactive_member = make_user(role=Role.HUB_MANAGER)
    outsider = make_user(role=Role.HUB_MANAGER)
    hub = _hub("LOW-004", manager=manager)
    HubMembership.objects.create(hub=hub, user=inactive_member, is_active=False)
    product = _product()
    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=5)

    with pytest.raises(PermissionDenied):
        record_movement(
            hub=hub,
            product=product,
            kind="ISSUE",
            quantity=2,
            actor=inactive_member,
        )
    with pytest.raises(PermissionDenied):
        record_movement(
            hub=hub,
            product=product,
            kind="ISSUE",
            quantity=2,
            actor=outsider,
        )

    assert not Notification.objects.exists()
    record_movement(
        hub=hub,
        product=product,
        kind="ISSUE",
        quantity=2,
        actor=manager,
    )
    assert Notification.objects.filter(recipient=manager).count() == 1
