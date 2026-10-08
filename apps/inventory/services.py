from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.roles import Role
from apps.audit.services import record_event
from apps.hubs.permissions import user_can_access_hub
from apps.notifications.services import create_notification
from apps.products.models import Product

from .models import (
    InventoryBalance,
    InventoryTransaction,
    PurchaseOrder,
    PurchaseOrderLine,
    Supplier,
)


DEFAULT_DIRECTIONS = {
    InventoryTransaction.Kind.RECEIPT: InventoryTransaction.Direction.IN,
    InventoryTransaction.Kind.ISSUE: InventoryTransaction.Direction.OUT,
    InventoryTransaction.Kind.SALE: InventoryTransaction.Direction.OUT,
    InventoryTransaction.Kind.REFUND: InventoryTransaction.Direction.IN,
}


def _notify_hub_managers_of_low_stock(*, hub, product, quantity):
    recipients = {}
    if hub.manager_id:
        recipients[hub.manager_id] = hub.manager
    for membership in hub.memberships.filter(
        is_active=True,
        user__role=Role.HUB_MANAGER,
    ).select_related("user"):
        recipients[membership.user_id] = membership.user

    for recipient in recipients.values():
        create_notification(
            recipient=recipient,
            title="Low stock alert",
            message=(
                f"{product.name} at {hub.name} has reached its reorder level "
                f"({quantity} remaining; reorder level: {product.reorder_level})."
            ),
            target_url="/inventory/",
        )


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
    previous_quantity = balance.quantity

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
    if previous_quantity > locked_product.reorder_level >= balance.quantity:
        _notify_hub_managers_of_low_stock(
            hub=hub,
            product=locked_product,
            quantity=balance.quantity,
        )
    return movement


@transaction.atomic
def create_reorder_order(*, hub, supplier, actor, notes=""):
    from django.core.exceptions import PermissionDenied

    if not actor.has_perm("inventory.add_purchaseorder"):
        raise PermissionDenied
    if not user_can_access_hub(actor, hub):
        raise PermissionDenied
    if hub.status != hub.Status.ACTIVE:
        raise ValidationError({"hub": "Purchase orders need an active hub."})
    if not supplier.is_active:
        raise ValidationError({"supplier": "Choose an active supplier."})

    reorder_products = list(
        Product.objects.select_for_update()
        .filter(
            is_active=True,
            reorder_level__gt=0,
        )
        .order_by("name")
    )
    hub_quantities = dict(
        InventoryBalance.objects.filter(
            hub=hub,
            product_id__in=[product.pk for product in reorder_products],
        ).values_list("product_id", "quantity")
    )
    low_stock_products = [
        product
        for product in reorder_products
        if hub_quantities.get(product.pk, 0) <= product.reorder_level
    ]
    if not low_stock_products:
        raise ValidationError("This hub has no active products at or below their reorder levels.")

    order = PurchaseOrder.objects.create(
        hub=hub,
        supplier=supplier,
        status=PurchaseOrder.Status.ORDERED,
        created_by=actor,
        notes=notes.strip(),
    )
    PurchaseOrderLine.objects.bulk_create([
        PurchaseOrderLine(
            order=order,
            product=product,
            quantity_ordered=max(
                product.reorder_level * 2 - hub_quantities.get(product.pk, 0),
                1,
            ),
            unit_cost=product.cost_price,
        )
        for product in low_stock_products
    ])
    record_event(
        action="inventory.purchase_order.created",
        summary=f"Created purchase order #{order.pk} for {hub}",
        actor=actor,
        target=order,
        changes={"supplier": supplier.name, "line_count": len(low_stock_products)},
    )
    return order


@transaction.atomic
def receive_purchase_order(*, order_id, quantities, actor):
    from django.core.exceptions import PermissionDenied

    if not actor.has_perm("inventory.change_purchaseorder"):
        raise PermissionDenied
    order = PurchaseOrder.objects.select_for_update().select_related("hub").get(pk=order_id)
    if not user_can_access_hub(actor, order.hub):
        raise PermissionDenied
    if order.status == PurchaseOrder.Status.RECEIVED:
        raise ValidationError("This purchase order has already been fully received.")

    lines = list(order.lines.select_for_update().select_related("product").order_by("pk"))
    known_ids = {line.pk for line in lines}
    if set(quantities) != known_ids:
        raise ValidationError("The purchase order lines changed. Reload and try again.")
    received_any = False
    for line in lines:
        quantity = quantities[line.pk]
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
            raise ValidationError("Received quantities must be whole numbers of zero or more.")
        if quantity > line.quantity_remaining:
            raise ValidationError(
                f"Received quantity for {line.product} exceeds the outstanding amount."
            )
        if quantity:
            record_movement(
                hub=order.hub,
                product=line.product,
                kind=InventoryTransaction.Kind.RECEIPT,
                quantity=quantity,
                unit_cost=line.unit_cost,
                reference=f"PO-{order.pk}",
                notes=f"Purchase order #{order.pk}",
                actor=actor,
            )
            line.quantity_received += quantity
            line.save(update_fields=["quantity_received"])
            received_any = True
    if not received_any:
        raise ValidationError("Enter at least one quantity to receive.")

    complete = all(line.quantity_received == line.quantity_ordered for line in lines)
    order.status = (
        PurchaseOrder.Status.RECEIVED
        if complete
        else PurchaseOrder.Status.PARTIALLY_RECEIVED
    )
    if complete:
        order.received_at = timezone.now()
        order.save(update_fields=["status", "received_at"])
    else:
        order.save(update_fields=["status"])
    record_event(
        action="inventory.purchase_order.received",
        summary=f"Received stock against purchase order #{order.pk}",
        actor=actor,
        target=order,
        changes={"status": order.status},
    )
    return order
