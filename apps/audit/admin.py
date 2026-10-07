from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "object_type", "object_id", "summary", "ip_address")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "action", "object_type", "object_id", "summary")
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False