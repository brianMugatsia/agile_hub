"""Roles and the permission matrix.

Each role is a Django Group with the same name. Permissions are listed by codename,
so entries for models that do not exist yet are skipped until that stage is built
(they are re-applied automatically after every `migrate`).

Models built later must declare these custom permissions in Meta.permissions:
  Sale:                    cancel_sale, refund_sale
  SalesAgentCommission:    approve_/reject_/pay_/reverse_salesagentcommission
  SalaryRecord:            approve_salaryrecord, pay_salaryrecord

NOTE: holding `view_<model>` only opens the page. Row-level scoping (own hub, own
sales, own salary) is enforced in selectors and views, never by permissions alone.
"""
from django.db import models


class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    ADMIN = "ADMIN", "Admin"
    HUB_MANAGER = "HUB_MANAGER", "Hub Manager"
    FINANCE_OFFICER = "FINANCE_OFFICER", "Finance Officer"
    SALES_AGENT = "SALES_AGENT", "Sales Agent"
    WORKER = "WORKER", "Worker"
    BENEFICIARY = "BENEFICIARY", "Beneficiary"
    VIEWER = "VIEWER", "Viewer"


# Which roles an actor may hand out. Roles absent here cannot assign any.
ROLE_ASSIGNMENT = {
    Role.SUPER_ADMIN: tuple(Role.values),
    Role.ADMIN: (
        Role.HUB_MANAGER,
        Role.FINANCE_OFFICER,
        Role.SALES_AGENT,
        Role.WORKER,
        Role.BENEFICIARY,
        Role.VIEWER,
    ),
}


def assignable_roles(actor):
    return ROLE_ASSIGNMENT.get(getattr(actor, "role", None), ())


def role_choices_for(actor):
    allowed = assignable_roles(actor)
    return [(value, label) for value, label in Role.choices if value in allowed]


# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------
ALL_PERMISSIONS = None  # sentinel: every permission in the system


def perms(model, *actions):
    return [f"{action}_{model}" for action in actions]


FINANCE_MODELS = (
    "beneficiaryprofile", "business", "revenuestream", "incomestatement",
    "incomestatementitem", "cashflow", "asset", "liability", "equityrecord",
    "projection", "startupcost", "fundingsource",
)


def _finance(*actions, models=FINANCE_MODELS):
    return [code for model in models for code in perms(model, *actions)]


ROLE_PERMISSIONS = {
    Role.SUPER_ADMIN: ALL_PERMISSIONS,
    Role.ADMIN: [
        *perms("user", "view", "add", "change"), "assign_roles",
        *perms("hub", "view", "change"),
        *perms("hubmembership", "view", "add", "change", "delete"),
        *perms("product", "view", "add", "change"),
        *perms("productpricehistory", "view"),
        *perms("inventorytransaction", "view", "add"),
        *perms("sale", "view"), *perms("saleitem", "view"),
        *perms("commissionsetting", "view"),
        *perms("salesagentcommission", "view", "approve", "reject"),
        *perms("workerprofile", "view", "add", "change"),
        *perms("salaryrecord", "view", "add", "change", "approve"),
        *_finance("view"),
        "export_reports",
    ],
    Role.HUB_MANAGER: [
        *perms("hub", "view", "change"),
        *perms("hubmembership", "view", "add", "change"),
        *perms("product", "view"),
        *perms("inventorytransaction", "view", "add"),
        *perms("sale", "view", "add", "change", "cancel"),
        *perms("saleitem", "view", "add", "change"),
        *perms("salesagentcommission", "view"),
        *perms("workerprofile", "view", "add", "change"),
        *perms("salaryrecord", "view"),
        *_finance("view"),
        *_finance("add", "change", models=("cashflow", "incomestatement", "incomestatementitem")),
    ],
    Role.FINANCE_OFFICER: [
        *perms("hub", "view"),
        *perms("product", "view"),
        *perms("inventorytransaction", "view"),
        *perms("sale", "view"), *perms("saleitem", "view"),
        *perms("commissionsetting", "view"),
        *perms("salesagentcommission", "view", "approve", "reject", "pay", "reverse"),
        *perms("workerprofile", "view"),
        *perms("salaryrecord", "view", "add", "change", "approve", "pay"),
        *_finance("view"),
        *_finance("add", "change", models=("cashflow",)),
        "export_reports",
    ],
    Role.SALES_AGENT: [
        *perms("product", "view"),
        *perms("sale", "view", "add"), *perms("saleitem", "view", "add"),
        *perms("salesagentcommission", "view"),
    ],
    Role.WORKER: [
        *perms("workerprofile", "view"),
        *perms("salaryrecord", "view"),
    ],
    Role.BENEFICIARY: [
        *_finance("view", "add", "change", models=("beneficiaryprofile", "business")),
        *_finance("view", "add", "change", "delete",
                  models=tuple(m for m in FINANCE_MODELS if m not in ("beneficiaryprofile", "business"))),
    ],
    Role.VIEWER: [
        *perms("hub", "view"),
        *perms("product", "view"),
        *perms("inventorytransaction", "view"),
        *perms("sale", "view"),
        *_finance("view"),
    ],
}

for _role, _permissions in ROLE_PERMISSIONS.items():
    if _permissions is not ALL_PERMISSIONS and "view_notification" not in _permissions:
        _permissions.append("view_notification")