from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.finance.models import CashFlow
from apps.hubs.permissions import user_can_access_hub
from apps.notifications.services import create_notification

from .models import SalaryRecord


@transaction.atomic
def approve_salary(*, salary_id, actor):
    if not actor.has_perm("payroll.approve_salaryrecord"):
        raise PermissionDenied
    salary = SalaryRecord.objects.select_for_update().get(pk=salary_id)
    if not user_can_access_hub(actor, salary.worker.hub):
        raise PermissionDenied
    if salary.status != SalaryRecord.Status.PENDING:
        raise ValidationError("Only pending salary records can be approved.")
    salary.status = SalaryRecord.Status.APPROVED
    salary.approved_by = actor
    salary.save(update_fields=["status", "approved_by"])
    record_event(action="payroll.salary_approved", summary=f"Salary approved for {salary.worker}",
                 actor=actor, target=salary, changes={"net_amount": str(salary.net_amount)})
    create_notification(
        recipient=salary.worker.user,
        title="Salary approved",
        message=f"Your salary for {salary.period_start:%B %Y} has been approved.",
        target_url="/payroll/salaries/",
    )
    return salary


@transaction.atomic
def pay_salary(*, salary_id, actor):
    if not actor.has_perm("payroll.pay_salaryrecord"):
        raise PermissionDenied
    salary = SalaryRecord.objects.select_for_update().select_related("worker__hub").get(pk=salary_id)
    if not user_can_access_hub(actor, salary.worker.hub):
        raise PermissionDenied
    if salary.status != SalaryRecord.Status.APPROVED:
        raise ValidationError("Only approved salary records can be paid.")
    salary.status = SalaryRecord.Status.PAID
    salary.paid_by = actor
    salary.paid_at = timezone.now()
    salary.save(update_fields=["status", "paid_by", "paid_at"])
    CashFlow.objects.create(
        direction=CashFlow.Direction.OUTFLOW,
        category="Payroll",
        amount=salary.net_amount,
        transaction_date=timezone.localdate(),
        hub=salary.worker.hub,
        reference=f"salary:{salary.pk}",
        description=f"Salary payment for {salary.worker} ({salary.period_start:%Y-%m})",
        created_by=actor,
    )
    record_event(action="payroll.salary_paid", summary=f"Salary paid to {salary.worker}",
                 actor=actor, target=salary, changes={"net_amount": str(salary.net_amount)})
    create_notification(
        recipient=salary.worker.user,
        title="Salary paid",
        message=f"Your salary payment of {salary.net_amount} has been recorded.",
        target_url="/payroll/salaries/",
    )
    return salary