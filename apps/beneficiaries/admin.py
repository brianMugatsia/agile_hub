from django.contrib import admin

from .models import BeneficiaryProfile, Business


@admin.register(BeneficiaryProfile)
class BeneficiaryProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "hub", "phone_number", "national_id")
    search_fields = ("user__username", "user__first_name", "user__last_name", "phone_number")
    autocomplete_fields = ("user",)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "beneficiary", "hub", "business_type", "status")
    list_filter = ("status", "business_type")
    search_fields = ("name", "registration_number", "beneficiary__user__username")
    autocomplete_fields = ("beneficiary",)