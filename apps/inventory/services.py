from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import record_event
from apps.hubs.permissions import user_can_access_hub
from apps.products.models import Product

from .models import InventoryBalance, InventoryTransaction


DEFAULT_DIRECTIONS = {
    InventoryTransaction.Kind.RECEIPT: InventoryTransaction.Direction.IN,
    InventoryTransaction.Kind.ISSUE: InventoryTransaction.Direction.OUT,
    InventoryTransaction.Kind.SALE: InventoryTransaction.Direction.OUT,
    InventoryTransaction.Kind.REFUND: InventoryTransaction.Direction.IN,
}


@transaction.atomic
def record_movement(
    *,
    hub,
    product,
    kind,
    quantity,
    actor=None,
    direction=None,
    unit_cost=None,
    reference="",
    notes="",
):
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be a positive whole number."})
    if kind not in InventoryTransaction.Kind.values:
        raise ValidationError({"kind": "Choose a valid inventory transaction type."})
    if actor is not None and not user_can_access_hub(actor, hub):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    if hub.status != hub.Status.ACTIVE:
        raise ValidationError({"hub": "Stock movements cannot be recorded for an inactive hub."})

    expected_direction = DEFAULT_DIRECTIONS.get(kind)
    direction = direction or expected_direction
    if direction not in InventoryTransaction.Direction.values:
        raise ValidationError({"direction": "Adjustments require an in or out direction."})
    if expected_direction and direction != expected_direction:
        raise ValidationError({"direction": "This transaction type cannot use that stock direction."})

    locked_product = Product.objects.select_for_update().get(pk=product.pk)
    balance, _ = InventoryBalance.objects.get_or_create(hub=hub, product=locked_product)
    balance = InventoryBalance.objects.select_for_update().get(pk=balance.pk)

    if direction == InventoryTransaction.Direction.OUT and balance.quantity < quantity:
        raise ValidationError(
            {"quantity": f"Only {balance.quantity} {locked_product.unit} are available at {hub}."}
        )

    if direction == InventoryTransaction.Direction.IN:
        balance.quantity += quantity
        locked_product.stock_on_hand += quantity
    else:
        balance.quantity -= quantity
        locked_product.stock_on_hand -= quantity
    balance.save(update_fields=["quantity", "updated_at"])
    locked_product.save(update_fields=["stock_on_hand", "updated_at"])

    movement = InventoryTransaction.objects.create(
        hub=hub,
        product=locked_product,
        kind=kind,
        direction=direction,
        quantity=quantity,
        unit_cost=unit_cost if unit_cost is not None else locked_product.cost_price,
        reference=reference,
        notes=notes,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    record_event(
        action="inventory.movement",
        summary=f"{movement.get_direction_display()} {quantity} {locked_product.unit} of {locked_product}",
        actor=actor,
        target=movement,
        changes={"kind": kind, "quantity": quantity, "direction": direction, "hub": str(hub.pk)},
    )
    return movement