from django.db.models import Q
from django.core.exceptions import FieldDoesNotExist

from apps.accounts.roles import Role
from apps.hubs.models import HubMembership


def _has_field(model, name):
    try:
        model._meta.get_field(name)
    except FieldDoesNotExist:
        return False
    return True


def scope_queryset(queryset, user):
    """Apply tenant and personal-record boundaries shared by HTML and API views."""
    model = queryset.model
    role = getattr(user, "role", None)

    if _has_field(model, "recipient"):
        queryset = queryset.filter(recipient=user)

    if role in (Role.SUPER_ADMIN, Role.ADMIN):
        return queryset

    if role == Role.SALES_AGENT:
        if _has_field(model, "agent"):
            queryset = queryset.filter(agent=user)
        elif _has_field(model, "sale"):
            queryset = queryset.filter(sale__agent=user)

    elif role == Role.WORKER:
        if _has_field(model, "user"):
            queryset = queryset.filter(user=user)
        elif _has_field(model, "worker"):
            queryset = queryset.filter(worker__user=user)

    elif role == Role.BENEFICIARY:
        if _has_field(model, "user"):
            queryset = queryset.filter(user=user)
        elif _has_field(model, "beneficiary"):
            queryset = queryset.filter(beneficiary__user=user)
        elif _has_field(model, "business"):
            queryset = queryset.filter(business__beneficiary__user=user)
        elif _has_field(model, "statement"):
            queryset = queryset.filter(statement__business__beneficiary__user=user)

    if role in (Role.HUB_MANAGER, Role.FINANCE_OFFICER, Role.VIEWER):
        hub_ids = HubMembership.objects.filter(user=user, is_active=True).values_list("hub_id", flat=True)
        managed_hub_ids = user.managed_hubs.values_list("pk", flat=True)
        if _has_field(model, "hub"):
            queryset = queryset.filter(Q(hub_id__in=hub_ids) | Q(hub_id__in=managed_hub_ids))
        elif _has_field(model, "worker"):
            queryset = queryset.filter(
                Q(worker__hub_id__in=hub_ids) | Q(worker__hub_id__in=managed_hub_ids)
            )
        elif _has_field(model, "sale"):
            queryset = queryset.filter(
                Q(sale__hub_id__in=hub_ids) | Q(sale__hub_id__in=managed_hub_ids)
            )
        elif _has_field(model, "statement"):
            queryset = queryset.filter(
                Q(statement__hub_id__in=hub_ids)
                | Q(statement__hub_id__in=managed_hub_ids)
                | Q(statement__business__hub_id__in=hub_ids)
                | Q(statement__business__hub_id__in=managed_hub_ids)
            )
        elif model._meta.model_name == "hub":
            queryset = queryset.filter(
                Q(manager=user) | Q(memberships__user=user, memberships__is_active=True)
            )
        elif model._meta.model_name == "hubmembership":
            queryset = queryset.filter(Q(hub__manager=user) | Q(hub_id__in=hub_ids))

    return queryset.distinct()
