import json
import logging

from django.conf import settings

logger = logging.getLogger("audit")


class AuditAction:
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED"


def get_client_ip(request):
    if request is None:
        return None
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(*, user, action, model_name, object_id=None,
               previous_data=None, new_data=None, request=None):
    """Write a durable audit event and emit a structured application log."""
    from .models import AuditLog

    ip_address = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""
    payload = {
        "user": str(getattr(user, "pk", "") or ""),
        "action": action,
        "model": model_name,
        "object_id": str(object_id) if object_id is not None else None,
        "previous": previous_data,
        "new": new_data,
        "ip": ip_address,
        "user_agent": user_agent,
    }
    logger.info("%s", json.dumps(payload, default=str))
    return AuditLog.objects.create(
        actor=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        object_type=model_name,
        object_id=str(object_id) if object_id is not None else "",
        summary=f"{action.replace('_', ' ').title()}: {model_name} {object_id or ''}".strip(),
        changes={
            "previous": previous_data or {},
            "new": new_data or {},
            "user_agent": user_agent,
        },
        ip_address=ip_address,
    )