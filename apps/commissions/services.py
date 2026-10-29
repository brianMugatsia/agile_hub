from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.finance.models import CashFlow
from apps.finance.services.calculations import get_active_financial_setting
from apps.hubs.permissions import user_can_access_hub
from apps.notifications.services import create_notification

from .models import CommissionSetting, SalesAgentCommission, ServiceCommission, CommissionPayment

CENT = Decimal("0.01")


def commission_rate_for(day=None):
    day = day or timezone.localdate()
    setting = CommissionSetting.objects.filter(is_active=True, effective_from__lte=day).first()
    if setting and setting.sales_agent_rate is not None:
        return setting.sales_agent_rate
    fin_setting = get_active_financial_setting(day)
    return getattr(fin_setting, "default_commission_rate", Decimal("0.00"))


@transaction.atomic
def accrue_for_sale(sale):
    rate = commission_rate_for(sale.completed_at.date() if sale.completed_at else None)
    agent = sale.agent or (sale.member.user if sale.member else None)
    commission, created = SalesAgentCommission.objects.get_or_create(
        sale=sale,
        defaults={
            "agent": agent,
            "rate": rate,
            "base_amount": sale.total,
            "amount": (sale.total * rate).quantize(CENT, rounding=ROUND_HALF_UP),
        },
    )
    if created and agent:
        record_event(
            action="commission.accrued",
            summary=f"Commission accrued for {sale}",
            actor=sale.created_by,
            target=commission,
            changes={"amount": str(commission.amount), "rate": str(commission.rate)},
        )
        create_notification(
            recipient=agent,
            title="Commission accrued",
            message=f"A commission of {commission.amount} was recorded for {sale}.",
            target_url="/commissions/",
        )
    return commission


def _require(actor, permission):
    if not getattr(actor, "is_authenticated", False) or not actor.has_perm(permission):
        raise PermissionDenied


def _require_commission_scope(actor, commission):
    if commission.sale and not user_can_access_hub(actor, commission.sale.hub):
        raise PermissionDenied


@transaction.atomic
def approve_commission(*, commission_id, actor, custom_rate=None, custom_amount=None, mark_paid=False, notes=None):
    _require(actor, "commissions.approve_salesagentcommission")      
    commission = SalesAgentCommission.objects.select_for_update().select_related("sale__hub").get(pk=commission_id)
    _require_commission_scope(actor, commission)
    if commission.status not in (SalesAgentCommission.Status.PENDING, SalesAgentCommission.Status.APPROVED):
        raise ValidationError("Only pending commissions can be approved.")

    CENT = Decimal("0.01")
    if custom_rate is not None:
        rate_val = Decimal(str(custom_rate))
        if rate_val > Decimal("1"):
            rate_val = rate_val / Decimal("100")
        commission.rate = rate_val
        commission.amount = (commission.base_amount * rate_val).quantize(CENT, rounding=ROUND_HALF_UP)
    if custom_amount is not None:
        commission.amount = Decimal(str(custom_amount)).quantize(CENT, rounding=ROUND_HALF_UP)

    commission.status = SalesAgentCommission.Status.APPROVED
    commission.approved_by = actor
    update_fields = ["status", "approved_by", "rate", "amount"]
    if notes:
        commission.notes = notes
        update_fields.append("notes")
    commission.save(update_fields=update_fields)
    record_event(action="commission.approved", summary=f"Commission approved for {commission.agent}",
                 actor=actor, target=commission, changes={"amount": str(commission.amount), "rate": str(commission.rate)})

    if mark_paid:
        _require(actor, "commissions.pay_salesagentcommission")
        commission.status = SalesAgentCommission.Status.PAID
        commission.paid_by = actor
        commission.paid_at = timezone.now()
        commission.save(update_fields=["status", "paid_by", "paid_at"])
        hub = commission.sale.hub if commission.sale else None
        CashFlow.objects.create(
            direction=CashFlow.Direction.OUTFLOW,
            category="Commissions",
            amount=commission.amount,
            transaction_date=timezone.localdate(),
            hub=hub,
            reference=f"commission:{commission.pk}",
            description=f"Commission paid to {commission.agent}",
            created_by=actor,
        )
        record_event(action="commission.paid", summary=f"Commission paid to {commission.agent}",
                     actor=actor, target=commission, changes={"amount": str(commission.amount)})
        if commission.agent:
            create_notification(
                recipient=commission.agent,
                title="Commission paid",
                message=f"Your commission of {commission.amount} has been paid.",
                target_url=f"/commissions/{commission.pk}/",
            )
    else:
        if commission.agent:
            create_notification(
                recipient=commission.agent,
                title="Commission approved",
                message=f"Your commission of {commission.amount} is approved.",
                target_url=f"/commissions/{commission.pk}/",
            )
    return commission


@transaction.atomic
def reject_commission(*, commission_id, actor, notes=""):
    _require(actor, "commissions.reject_salesagentcommission")
    commission = SalesAgentCommission.objects.select_for_update().select_related("sale__hub").get(pk=commission_id)
    _require_commission_scope(actor, commission)
    if commission.status != SalesAgentCommission.Status.PENDING:
        raise ValidationError("Only pending commissions can be rejected.")
    commission.status = SalesAgentCommission.Status.REJECTED
    commission.notes = notes.strip()
    commission.approved_by = actor
    commission.save(update_fields=["status", "notes", "approved_by"])
    record_event(action="commission.rejected", summary=f"Commission rejected for {commission.agent}",
                 actor=actor, target=commission, changes={"notes": notes.strip()})
    if commission.agent:
        create_notification(
            recipient=commission.agent,
            title="Commission rejected",
            message=f"Your commission of {commission.amount} was rejected.",
            target_url=f"/commissions/{commission.pk}/",
        )
    return commission


@transaction.atomic
def pay_commission(*, commission_id, actor):
    _require(actor, "commissions.pay_salesagentcommission")
    commission = SalesAgentCommission.objects.select_for_update().select_related("sale__hub").get(pk=commission_id)
    _require_commission_scope(actor, commission)
    if commission.status != SalesAgentCommission.Status.APPROVED:
        raise ValidationError("Only approved commissions can be paid.")
    commission.status = SalesAgentCommission.Status.PAID
    commission.paid_by = actor
    commission.paid_at = timezone.now()
    commission.save(update_fields=["status", "paid_by", "paid_at"])
    hub = commission.sale.hub if commission.sale else None
    CashFlow.objects.create(
        direction=CashFlow.Direction.OUTFLOW,
        category="Commissions",
        amount=commission.amount,
        transaction_date=timezone.localdate(),
        hub=hub,
        reference=f"commission:{commission.pk}",
        description=f"Commission paid to {commission.agent}",
        created_by=actor,
    )
    record_event(action="commission.paid", summary=f"Commission paid to {commission.agent}",
                 actor=actor, target=commission, changes={"amount": str(commission.amount)})
    if commission.agent:
        create_notification(
            recipient=commission.agent,
            title="Commission paid",
            message=f"Your commission of {commission.amount} has been paid.",
            target_url=f"/commissions/{commission.pk}/",
        )
    return commission


@transaction.atomic
def reverse_commission(*, commission_id, actor, notes=""):
    _require(actor, "commissions.reverse_salesagentcommission")
    commission = SalesAgentCommission.objects.select_for_update().select_related("sale__hub").get(pk=commission_id)
    _require_commission_scope(actor, commission)
    if commission.status in (SalesAgentCommission.Status.REVERSED, SalesAgentCommission.Status.REJECTED):
        raise ValidationError("This commission cannot be reversed.")
    commission.status = SalesAgentCommission.Status.REVERSED
    commission.notes = "\n".join(part for part in (commission.notes, notes.strip()) if part)
    commission.save(update_fields=["status", "notes"])
    record_event(action="commission.reversed", summary=f"Commission reversed for {commission.agent}",
                 actor=actor, target=commission, changes={"notes": notes.strip()})
    return commission


@transaction.atomic
def accrue_service_commission(booking, custom_rate=None, custom_amount=None):
    if not booking.service_provider:
        return None
    day = booking.start_date.date() if booking.start_date else timezone.localdate()
    com_setting = CommissionSetting.objects.filter(is_active=True, effective_from__lte=day).first()
    setting = get_active_financial_setting(day)
    provider_type = booking.service_provider.provider_type
    
    if custom_rate is not None:
        rate = Decimal(str(custom_rate))
    elif provider_type == "INTERNAL":
        rate = (com_setting.internal_provider_rate if (com_setting and com_setting.internal_provider_rate is not None) else None)
        if rate is None:
            rate = setting.internal_commission_rate
    else:
        rate = (com_setting.external_provider_rate if (com_setting and com_setting.external_provider_rate is not None) else None)
        if rate is None:
            rate = setting.external_commission_rate

    base_amount = booking.total_amount
    if custom_amount is not None:
        amount = Decimal(str(custom_amount)).quantize(CENT, rounding=ROUND_HALF_UP)
    else:
        amount = (base_amount * rate).quantize(CENT, rounding=ROUND_HALF_UP)

    commission, created = ServiceCommission.objects.update_or_create(
        provider=booking.service_provider,
        booking=booking,
        defaults={
            "provider_type": provider_type,
            "service_type": booking.service_type,
            "rate": rate,
            "calculation_basis": setting.commission_calculation_basis,
            "base_amount": base_amount,
            "amount": amount,
            "status": ServiceCommission.Status.PENDING,
        },
    )
    if created:
        record_event(
            action="service_commission.accrued",
            summary=f"Service commission accrued for booking {booking}",
            target=commission,
            changes={"amount": str(commission.amount), "rate": str(commission.rate)},
        )
    return commission


@transaction.atomic
def approve_service_commission(*, commission_id, actor):
    if actor and not actor.has_perm("commissions.approve_servicecommission"):
        raise PermissionDenied("You do not have permission to approve service commissions.")
    commission = ServiceCommission.objects.select_for_update().get(pk=commission_id)
    if commission.status != ServiceCommission.Status.PENDING:
        raise ValidationError("Only pending commissions can be approved.")
    commission.status = ServiceCommission.Status.APPROVED
    commission.approved_by = actor
    commission.save(update_fields=["status", "approved_by", "updated_at"])
    record_event(
        action="service_commission.approved",
        summary=f"Service commission approved for {commission.provider}",
        actor=actor,
        target=commission,
        changes={"amount": str(commission.amount)},
    )
    return commission


@transaction.atomic
def reject_service_commission(*, commission_id, actor, notes=""):
    if actor and not actor.has_perm("commissions.reject_servicecommission"):
        raise PermissionDenied("You do not have permission to reject service commissions.")
    commission = ServiceCommission.objects.select_for_update().get(pk=commission_id)
    if commission.status != ServiceCommission.Status.PENDING:
        raise ValidationError("Only pending commissions can be rejected.")
    commission.status = ServiceCommission.Status.REJECTED
    commission.notes = notes.strip()
    commission.approved_by = actor
    commission.save(update_fields=["status", "notes", "approved_by", "updated_at"])
    record_event(
        action="service_commission.rejected",
        summary=f"Service commission rejected for {commission.provider}",
        actor=actor,
        target=commission,
        changes={"notes": notes.strip()},
    )
    return commission


@transaction.atomic
def pay_service_commission(*, commission_id, actor, payment_reference=""):
    if actor and not actor.has_perm("commissions.pay_servicecommission"):
        raise PermissionDenied("You do not have permission to pay service commissions.")
    commission = ServiceCommission.objects.select_for_update().get(pk=commission_id)
    if commission.status != ServiceCommission.Status.APPROVED:
        raise ValidationError("Only approved commissions can be paid.")

    commission.status = ServiceCommission.Status.PAID
    commission.paid_by = actor
    commission.paid_at = timezone.now()
    commission.save(update_fields=["status", "paid_by", "paid_at", "updated_at"])

    payment = CommissionPayment.objects.create(
        amount=commission.amount,
        payment_date=timezone.localdate(),
        payment_reference=payment_reference.strip(),
        paid_by=actor,
    )
    payment.commissions.add(commission)

    hub = commission.booking.hub if commission.booking else None
    CashFlow.objects.create(
        direction=CashFlow.Direction.OUTFLOW,
        category="Service Provider Commissions",
        amount=commission.amount,
        transaction_date=timezone.localdate(),
        hub=hub,
        reference=f"service_commission:{commission.pk}",
        description=f"Commission paid to service provider {commission.provider}",
        created_by=actor,
    )

    record_event(
        action="service_commission.paid",
        summary=f"Service commission paid to {commission.provider}",
        actor=actor,
        target=commission,
        changes={"amount": str(commission.amount)},
    )
    return commission


@transaction.atomic
def reverse_service_commission(*, commission_id, actor, notes=""):
    if actor and not actor.has_perm("commissions.reverse_servicecommission"):
        raise PermissionDenied("You do not have permission to reverse service commissions.")
    commission = ServiceCommission.objects.select_for_update().get(pk=commission_id)
    if commission.status in (ServiceCommission.Status.REVERSED, ServiceCommission.Status.REJECTED):
        raise ValidationError("This commission cannot be reversed.")
    commission.status = ServiceCommission.Status.REVERSED
    commission.notes = "\n".join(part for part in (commission.notes, notes.strip()) if part)
    commission.save(update_fields=["status", "notes", "updated_at"])
    record_event(
        action="service_commission.reversed",
        summary=f"Service commission reversed for {commission.provider}",
        actor=actor,
        target=commission,
        changes={"notes": notes.strip()},
    )
    return commission
