from django.contrib import admin
from .models import HubResource, ServiceBooking, ServiceType


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "pricing_unit", "standard_rate", "is_active")
    list_filter = ("category", "pricing_unit", "is_active")
    search_fields = ("code", "name")


@admin.register(HubResource)
class HubResourceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "hub", "service_type", "capacity", "capacity_unit", "status", "operator_name")
    list_filter = ("status", "hub", "service_type__category")
    search_fields = ("code", "name", "operator_name")


@admin.register(ServiceBooking)
class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "hub",
        "service_type",
        "resource",
        "client_display",
        "start_date",
        "total_amount",
        "status",
        "payment_status",
    )
    list_filter = ("status", "payment_status", "hub", "service_type__category")
    search_fields = ("customer_name", "customer_phone", "payment_reference")
