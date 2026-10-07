from django.contrib import admin

from .models import InventoryBalance, InventoryTransaction


@admin.register(InventoryBalance)
class InventoryBalanceAdmin(admin.ModelAdmin):
    list_display = ("hub", "product", "quantity", "updated_at")
    list_filter = ("hub",)
    search_fields = ("hub__name", "product__sku", "product__name")
    readonly_fields = tuple(field.name for field in InventoryBalance._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "hub", "product", "kind", "direction", "quantity", "reference")
    list_filter = ("kind", "direction", "hub", "created_at")
    search_fields = ("product__sku", "product__name", "reference")
    readonly_fields = tuple(field.name for field in InventoryTransaction._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False