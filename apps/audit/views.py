from apps.core.generic import ScopedModelListView
from apps.core.exports import ScopedModelExportView

from .models import AuditLog


class AuditListView(ScopedModelListView):
    model = AuditLog
    page_title = "Audit trail"
    export_url_name = "audit:export"
    columns = (
        {"label": "When", "field": "created_at"},
        {"label": "User", "field": "actor__display_name"},
        {"label": "Action", "field": "action"},
        {"label": "Record", "field": "object_type"},
        {"label": "Summary", "field": "summary"},
        {"label": "IP address", "field": "ip_address"},
    )
    search_fields = ("action", "object_type", "summary")


class AuditExportView(ScopedModelExportView):
    list_view_class = AuditListView