from django.db.models import Q
from django.core.exceptions import FieldDoesNotExist

from apps.accounts.roles import Role
from apps.hubs.models import HubMembership
from apps.hubs.permissions import hubs_for_user


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

    # Single hub-locked scoping: if user.hub is set, use it; otherwise fall back to hubs_for_user(user)
    user_hub = getattr(user, "hub", None)
    if user_hub is not None:
        hub_ids = [user_hub.pk]
    else:
        hub_ids = list(hubs_for_user(user).values_list("pk", flat=True))

    if hub_ids is not None:
        if _has_field(model, "hub"):
            hub_scope = Q(hub_id__in=hub_ids)
            if _has_field(model, "business"):
                hub_scope |= Q(business__hub_id__in=hub_ids)
            queryset = queryset.filter(hub_scope)
        elif _has_field(model, "business"):
            queryset = queryset.filter(business__hub_id__in=hub_ids)
        elif _has_field(model, "worker"):
            queryset = queryset.filter(worker__hub_id__in=hub_ids)
        elif _has_field(model, "sale"):
            queryset = queryset.filter(sale__hub_id__in=hub_ids)
        elif _has_field(model, "statement"):
            queryset = queryset.filter(
                Q(statement__hub_id__in=hub_ids) | Q(statement__business__hub_id__in=hub_ids)
            )
        elif model._meta.model_name == "hub":
            queryset = queryset.filter(pk__in=hub_ids)
        elif model._meta.model_name == "hubmembership":
            queryset = queryset.filter(hub_id__in=hub_ids)

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

    elif role == Role.MEMBER:
        if _has_field(model, "user"):
            queryset = queryset.filter(user=user)
        elif _has_field(model, "member"):
            queryset = queryset.filter(member__user=user)
        elif _has_field(model, "business"):
            queryset = queryset.filter(business__member__user=user)
        elif _has_field(model, "statement"):
            queryset = queryset.filter(statement__business__member__user=user)

    return queryset.distinct()
