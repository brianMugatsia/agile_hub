from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.commissions.services import accrue_for_sale
from apps.finance.models import CashFlow
from apps.beneficiaries.models import Business
from apps.hubs.permissions import user_can_access_hub
from apps.inventory.models import InventoryTransaction
from apps.inventory.services import record_movement
from apps.products.models import Product

from .models import Sale, SaleItem

CENT = Decimal("0.01")


@transaction.atomic
def complete_sale(*, hub, agent, items, actor=None, customer_name="", customer_phone="",
                  payment_method=Sale.PaymentMethod.CASH, payment_reference="", notes="", business=None):
    normalized = {}
    for item in items:
        try:
            product_id = item["product"]
            quantity = item["quantity"]
        except (KeyError, TypeError) as exc:
            raise ValidationError("Each sale line needs a product and quantity.") from exc
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError({"quantity": "Sale quantities must be positive whole numbers."})
        key = str(product_id)
        if key in normalized:
            raise ValidationError("A product can appear only once on a sale.")
        normalized[key] = quantity
    if not normalized:
        raise ValidationError("Add at least one product to the sale.")
    if hub.status != hub.Status.ACTIVE:
        raise ValidationError({"hub": "This hub is not active."})
    if business is not None and business.hub_id and business.hub_id != hub.pk:
        raise ValidationError({"business": "The selected business belongs to a different hub."})
    if business is not None and business.status != Business.Status.ACTIVE:
        raise ValidationError({"business": "The selected business is not active."})
    if actor is not None:
        if not user_can_access_hub(actor, hub):
            raise PermissionDenied
        if actor.role not in ("SUPER_ADMIN", "ADMIN") and agent.pk != actor.pk:
            raise PermissionDenied

    products = list(Product.objects.select_for_update().filter(pk__in=normalized).order_by("pk"))
    if len(products) != len(normalized):
        raise ValidationError({"product": "One or more selected products no longer exist."})

    sale = Sale.objects.create(
        hub=hub,
        business=business,
        agent=agent,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        payment_method=payment_method,
        payment_reference=payment_reference.strip(),
        notes=notes.strip(),
    )
    total = Decimal("0.00")
    for product in products:
        quantity = normalized[str(product.pk)]
        if not product.is_active:
            raise ValidationError({"product": f"{product} is inactive."})
        item = SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_price=product.selling_price,
            unit_cost=product.cost_price,
        )
        record_movement(
            hub=hub,
            product=product,
            kind=InventoryTransaction.Kind.SALE,
            quantity=quantity,
            actor=actor,
            reference=str(sale.pk),
        )
        total += item.line_total

    sale.total = total.quantize(CENT, rounding=ROUND_HALF_UP)
    sale.status = Sale.Status.COMPLETED
    sale.completed_at = timezone.now()
    sale.save(update_fields=["total", "status", "completed_at", "updated_at"])
    if getattr(agent, "role", None) == "SALES_AGENT":
        accrue_for_sale(sale)
    if payment_method != Sale.PaymentMethod.CREDIT:
        CashFlow.objects.create(
            direction=CashFlow.Direction.INFLOW,
            category="Sales",
            amount=sale.total,
            transaction_date=timezone.localdate(),
            hub=hub,
            reference=f"sale:{sale.pk}",
            description=f"Payment received for {sale}",
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
    record_event(
        action="sale.completed",
        summary=f"Sale completed at {hub}",
        actor=actor,
        target=sale,
        changes={"total": str(sale.total), "line_count": len(normalized)},
    )
    return sale


@transaction.atomic
def cancel_sale(*, sale_id, actor, reason):
    if not actor.has_perm("sales.cancel_sale"):
        raise PermissionDenied
    if not reason.strip():
        raise ValidationError({"reason": "A reason is required."})
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if not user_can_access_hub(actor, sale.hub):
        raise PermissionDenied
    if sale.status != Sale.Status.DRAFT:
        raise ValidationError("Only draft sales can be cancelled. Completed sales must be refunded.")
    sale.status = Sale.Status.CANCELLED
    sale.notes = "\n".join(part for part in (sale.notes, f"Cancellation: {reason.strip()}") if part)
    sale.save(update_fields=["status", "notes", "updated_at"])
    record_event(action="sale.cancelled", summary=f"Sale cancelled: {sale}", actor=actor,
                 target=sale, changes={"reason": reason.strip()})
    return sale


@transaction.atomic
def refund_sale(*, sale_id, actor, reason):
    from django.core.exceptions import PermissionDenied

    if not actor.has_perm("sales.refund_sale"):
        raise PermissionDenied
    if not reason.strip():
        raise ValidationError({"reason": "A reason is required."})
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if not user_can_access_hub(actor, sale.hub):
        raise PermissionDenied
    if sale.status != Sale.Status.COMPLETED:
        raise ValidationError("Only completed sales can be refunded.")

    for item in sale.items.select_related("product").order_by("product_id"):
        record_movement(
            hub=sale.hub,
            product=item.product,
            kind=InventoryTransaction.Kind.REFUND,
            quantity=item.quantity,
            actor=actor,
            reference=str(sale.pk),
            notes=reason.strip(),
        )
    sale.status = Sale.Status.REFUNDED
    sale.notes = "\n".join(part for part in (sale.notes, f"Refund: {reason.strip()}") if part)
    sale.save(update_fields=["status", "notes", "updated_at"])
    if sale.payment_method != Sale.PaymentMethod.CREDIT:
        CashFlow.objects.create(
            direction=CashFlow.Direction.OUTFLOW,
            category="Sales refund",
            amount=sale.total,
            transaction_date=timezone.localdate(),
            hub=sale.hub,
            reference=f"refund:{sale.pk}",
            description=f"Refund issued for {sale}",
            created_by=actor,
        )
    commission = getattr(sale, "commission", None)
    if commission and commission.status not in ("REJECTED", "REVERSED"):
        commission.status = commission.Status.REVERSED
        commission.notes = reason.strip()
        commission.save(update_fields=["status", "notes"])
    record_event(action="sale.refunded", summary=f"Sale refunded: {sale}", actor=actor,
                 target=sale, changes={"reason": reason.strip(), "amount": str(sale.total)})
    return sale