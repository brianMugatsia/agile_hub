from django.contrib import admin

from .models import CommissionSetting, SalesAgentCommission


@admin.register(CommissionSetting)
class CommissionSettingAdmin(admin.ModelAdmin):
    list_display = ("rate", "effective_from", "is_active", "created_by")
    list_filter = ("is_active", "effective_from")


@admin.register(SalesAgentCommission)
class SalesAgentCommissionAdmin(admin.ModelAdmin):
    list_display = ("agent", "sale", "rate", "amount", "status", "paid_at")
    list_filter = ("status", "created_at")
    search_fields = ("agent__username", "sale__id", "sale__payment_reference")
    readonly_fields = tuple(field.name for field in SalesAgentCommission._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False