from django.contrib import admin

from .models import Product, ProductPriceHistory


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "category", "selling_price", "stock_on_hand", "is_active")
    list_filter = ("is_active", "category")
    search_fields = ("sku", "name", "category")
    readonly_fields = ("stock_on_hand",)


@admin.register(ProductPriceHistory)
class ProductPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("product", "previous_price", "new_price", "changed_by", "changed_at")
    list_filter = ("changed_at",)
    search_fields = ("product__sku", "product__name")
    readonly_fields = tuple(field.name for field in ProductPriceHistory._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False