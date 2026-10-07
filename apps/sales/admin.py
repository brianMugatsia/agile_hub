from django.contrib import admin

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "quantity", "unit_price", "unit_cost")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "hub", "agent", "total", "status", "payment_method")
    list_filter = ("status", "payment_method", "hub", "created_at")
    search_fields = ("id", "customer_name", "customer_phone", "payment_reference", "agent__username")
    readonly_fields = tuple(field.name for field in Sale._meta.fields)
    inlines = (SaleItemInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False