from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.finance.models import CashFlow
from apps.hubs.permissions import user_can_access_hub
from apps.notifications.services import create_notification

from .models import CommissionSetting, SalesAgentCommission

CENT = Decimal("0.01")


def commission_rate_for(day=None):
    day = day or timezone.localdate()
    setting = CommissionSetting.objects.filter(is_active=True, effective_from__lte=day).first()
    return setting.rate if setting else settings.DEFAULT_COMMISSION_RATE


@transaction.atomic
def accrue_for_sale(sale):
    rate = commission_rate_for(sale.completed_at.date() if sale.completed_at else None)
    commission, created = SalesAgentCommission.objects.get_or_create(
        sale=sale,
        defaults={
            "agent": sale.agent,
            "rate": rate,
            "base_amount": sale.total,
            "amount": (sale.total * rate).quantize(CENT, rounding=ROUND_HALF_UP),
        },
    )
    if created:
        record_event(
            action="commission.accrued",
            summary=f"Commission accrued for {sale}",
            actor=sale.created_by,
            target=commission,
            changes={"amount": str(commission.amount), "rate": str(commission.rate)},
        )
        create_notification(
            recipient=sale.agent,
            title="Commission accrued",
            message=f"A commission of {commission.amount} was recorded for {sale}.",
            target_url="/commissions/",
        )
    return commission


def _require(actor, permission):
    if not getattr(actor, "is_authenticated", False) or not actor.has_perm(permission):
        raise PermissionDenied


def _require_commission_scope(actor, commission):
    if not user_can_access_hub(actor, commission.sale.hub):
        raise PermissionDenied


@transaction.atomic
def approve_commission(*, commission_id, actor):
    _require(actor, "commissions.approve_salesagentcommission")
    commission = SalesAgentCommission.objects.select_for_update().get(pk=commission_id)
    _require_commission_scope(actor, commission)
    if commission.status != SalesAgentCommission.Status.PENDING:
        raise ValidationError("Only pending commissions can be approved.")
    commission.status = SalesAgentCommission.Status.APPROVED
    commission.approved_by = actor
    commission.save(update_fields=["status", "approved_by"])
    record_event(action="commission.approved", summary=f"Commission approved for {commission.agent}",
                 actor=actor, target=commission)
    create_notification(
        recipient=commission.agent,
        title="Commission approved",
        message=f"Your commission of {commission.amount} is approved.",
        target_url="/commissions/",
    )
    return commission


@transaction.atomic
def reject_commission(*, commission_id, actor, reason):
    _require(actor, "commissions.reject_salesagentcommission")
    if not reason.strip():
        raise ValidationError({"reason": "A reason is required."})
    commission = SalesAgentCommission.objects.select_for_update().get(pk=commission_id)
    _require_commission_scope(actor, commission)
    if commission.status != SalesAgentCommission.Status.PENDING:
        raise ValidationError("Only pending commissions can be rejected.")
    commission.status = SalesAgentCommission.Status.REJECTED
    commission.notes = reason.strip()
    commission.approved_by = actor
    commission.save(update_fields=["status", "notes", "approved_by"])
    record_event(action="commission.rejected", summary=f"Commission rejected for {commission.agent}",
                 actor=actor, target=commission, changes={"reason": reason.strip()})
    create_notification(
        recipient=commission.agent,
        title="Commission rejected",
        message=f"Your commission was rejected: {reason.strip()}",
        target_url="/commissions/",
    )
    return commission


@transaction.atomic
def pay_commission(*, commission_id, actor):
    _require(actor, "commissions.pay_salesagentcommission")
    commission = SalesAgentCommission.objects.select_for_update().get(pk=commission_id)
    _require_commission_scope(actor, commission)
    if commission.status != SalesAgentCommission.Status.APPROVED:
        raise ValidationError("Only approved commissions can be paid.")
    commission.status = SalesAgentCommission.Status.PAID
    commission.paid_by = actor
    commission.paid_at = timezone.now()
    commission.save(update_fields=["status", "paid_by", "paid_at"])
    CashFlow.objects.create(
        direction=CashFlow.Direction.OUTFLOW,
        category="Sales commission",
        amount=commission.amount,
        transaction_date=timezone.localdate(),
        hub=commission.sale.hub,
        reference=f"commission:{commission.pk}",
        description=f"Commission payment to {commission.agent}",
        created_by=actor,
    )
    record_event(action="commission.paid", summary=f"Commission paid to {commission.agent}",
                 actor=actor, target=commission, changes={"amount": str(commission.amount)})
    create_notification(
        recipient=commission.agent,
        title="Commission paid",
        message=f"Your commission payment of {commission.amount} has been recorded.",
        target_url="/commissions/",
    )
    return commission


@transaction.atomic
def reverse_commission(*, commission_id, actor, reason):
    _require(actor, "commissions.reverse_salesagentcommission")
    if not reason.strip():
        raise ValidationError({"reason": "A reason is required."})
    commission = SalesAgentCommission.objects.select_for_update().get(pk=commission_id)
    _require_commission_scope(actor, commission)
    if commission.status in (SalesAgentCommission.Status.REVERSED, SalesAgentCommission.Status.REJECTED):
        raise ValidationError("This commission has already been reversed or rejected.")
    commission.status = SalesAgentCommission.Status.REVERSED
    commission.notes = reason.strip()
    commission.save(update_fields=["status", "notes"])
    record_event(action="commission.reversed", summary=f"Commission reversed for {commission.agent}",
                 actor=actor, target=commission, changes={"reason": reason.strip()})
    create_notification(
        recipient=commission.agent,
        title="Commission reversed",
        message=f"Your commission was reversed: {reason.strip()}",
        target_url="/commissions/",
    )
    return commission