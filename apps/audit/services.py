from .models import AuditLog


def record_event(*, action, summary, actor=None, target=None, changes=None, ip_address=None, request=None):
    if ip_address is None and request is not None:
        from .utils import get_client_ip

        ip_address = get_client_ip(request)
    target_type = target._meta.label if target is not None else ""
    target_id = str(target.pk) if target is not None else ""
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_type=target_type,
        object_id=target_id,
        summary=summary,
        changes=changes or {},
        ip_address=ip_address,
    )