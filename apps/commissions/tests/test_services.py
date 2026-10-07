from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.roles import Role
from apps.commissions.models import SalesAgentCommission
from apps.commissions.services import approve_commission, pay_commission
from apps.finance.models import CashFlow
from apps.hubs.models import Hub, HubMembership
from apps.inventory.services import record_movement
from apps.products.models import Product
from apps.sales.services import complete_sale

pytestmark = pytest.mark.django_db


def test_commission_must_be_approved_before_payment(make_user, roles):
    hub = Hub.objects.create(code="H-COM", name="Commission Hub")
    agent = make_user(role=Role.SALES_AGENT)
    finance = make_user(role=Role.FINANCE_OFFICER)
    HubMembership.objects.create(hub=hub, user=agent)
    HubMembership.objects.create(hub=hub, user=finance)
    product = Product.objects.create(
        sku="COM-001",
        name="Seed pack",
        cost_price=Decimal("5.00"),
        selling_price=Decimal("20.00"),
    )
    record_movement(hub=hub, product=product, kind="RECEIPT", quantity=2)
    sale = complete_sale(
        hub=hub,
        agent=agent,
        items=[{"product": product.pk, "quantity": 1}],
        actor=agent,
    )
    commission = sale.commission

    with pytest.raises(ValidationError):
        pay_commission(commission_id=commission.pk, actor=finance)

    approve_commission(commission_id=commission.pk, actor=finance)
    pay_commission(commission_id=commission.pk, actor=finance)

    commission.refresh_from_db()
    assert commission.status == SalesAgentCommission.Status.PAID
    assert commission.approved_by == finance
    assert commission.paid_by == finance
    assert CashFlow.objects.filter(
        reference=f"commission:{commission.pk}",
        direction=CashFlow.Direction.OUTFLOW,
        amount=commission.amount,
    ).exists()