from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.roles import Role
from apps.finance.models import CashFlow
from apps.hubs.models import Hub, HubMembership
from apps.payroll.models import SalaryRecord, WorkerProfile
from apps.payroll.services import approve_salary, pay_salary

pytestmark = pytest.mark.django_db


def test_salary_requires_approval_and_payment_is_auditable(make_user, roles):
    hub = Hub.objects.create(code="H-PAY", name="Payroll Hub")
    worker_user = make_user(role=Role.WORKER)
    finance = make_user(role=Role.FINANCE_OFFICER)
    HubMembership.objects.create(hub=hub, user=finance)
    worker = WorkerProfile.objects.create(
        user=worker_user,
        hub=hub,
        employee_code="EMP-001",
        job_title="Field officer",
        monthly_salary=Decimal("1500.00"),
        hired_on=timezone.localdate(),
    )
    today = timezone.localdate()
    salary = SalaryRecord.objects.create(
        worker=worker,
        period_start=today.replace(day=1),
        period_end=today,
        gross_amount=Decimal("1500.00"),
        deductions=Decimal("100.00"),
        status=SalaryRecord.Status.PENDING,
    )

    with pytest.raises(ValidationError):
        pay_salary(salary_id=salary.pk, actor=finance)

    approve_salary(salary_id=salary.pk, actor=finance)
    pay_salary(salary_id=salary.pk, actor=finance)

    salary.refresh_from_db()
    assert salary.status == SalaryRecord.Status.PAID
    assert salary.net_amount == Decimal("1400.00")
    assert CashFlow.objects.filter(
        reference=f"salary:{salary.pk}",
        direction=CashFlow.Direction.OUTFLOW,
        amount=Decimal("1400.00"),
    ).exists()