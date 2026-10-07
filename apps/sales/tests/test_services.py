from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.roles import Role
from apps.finance.models import CashFlow
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryBalance
from apps.inventory.services import record_movement
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import complete_sale, refund_sale

pytestmark = pytest.mark.django_db


def _hub(code="H-001"):
    return Hub.objects.create(code=code, name=f"Hub {code}")


def _product(sku="SKU-001"):
    return Product.objects.create(
        sku=sku,
        name="Seed pack",
        cost_price=Decimal("4.00"),
        selling_price=Decimal("10.00"),
        stock_on_hand=0,
    )


def test_sale_completion_atomically_updates_stock_cash_and_commission(make_user, roles, settings):
    settings.DEFAULT_COMMISSION_RATE = Decimal("0.20")
    hub = _hub()
    agent = make_user(role=Role.SALES_AGENT)
    HubMembership.objects.create(hub=hub, user=agent)
    product = _product()
    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=5)

    sale = complete_sale(
        hub=hub,
        agent=agent,
        items=[{"product": product.pk, "quantity": 2}],
        actor=agent,
    )

    balance = InventoryBalance.objects.get(hub=hub, product=product)
    product.refresh_from_db()
    assert sale.status == Sale.Status.COMPLETED
    assert sale.total == Decimal("20.00")
    assert balance.quantity == product.stock_on_hand == 3
    assert sale.commission.amount == Decimal("4.00")
    assert CashFlow.objects.get(reference=f"sale:{sale.pk}").amount == sale.total


def test_sale_insufficient_stock_rolls_back_sale_and_all_side_effects(make_user, roles):
    hub = _hub()
    agent = make_user(role=Role.SALES_AGENT)
    HubMembership.objects.create(hub=hub, user=agent)
    product = _product()
    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=2)

    with pytest.raises(ValidationError):
        complete_sale(
            hub=hub,
            agent=agent,
            items=[{"product": product.pk, "quantity": 3}],
            actor=agent,
        )

    assert not Sale.objects.exists()
    assert not CashFlow.objects.exists()
    assert InventoryBalance.objects.get(hub=hub, product=product).quantity == 2
    product.refresh_from_db()
    assert product.stock_on_hand == 2


def test_refund_restores_stock_and_records_outflow_and_commission_reversal(make_user, roles):
    hub = _hub()
    agent = make_user(role=Role.SALES_AGENT)
    administrator = make_user(role=Role.SUPER_ADMIN)
    HubMembership.objects.create(hub=hub, user=agent)
    product = _product()
    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=5)
    sale = complete_sale(
        hub=hub,
        agent=agent,
        items=[{"product": product.pk, "quantity": 2}],
        actor=agent,
    )

    refund_sale(sale_id=sale.pk, actor=administrator, reason="Customer return")

    sale.refresh_from_db()
    product.refresh_from_db()
    assert sale.status == Sale.Status.REFUNDED
    assert InventoryBalance.objects.get(hub=hub, product=product).quantity == 5
    assert product.stock_on_hand == 5
    assert sale.commission.status == sale.commission.Status.REVERSED
    refund = CashFlow.objects.get(reference=f"refund:{sale.pk}")
    assert refund.direction == CashFlow.Direction.OUTFLOW
    assert refund.amount == sale.total