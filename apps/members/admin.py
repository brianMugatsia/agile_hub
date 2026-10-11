from django.contrib import admin

from .models import MemberProfile, Business


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "hub", "phone_number", "national_id")
    search_fields = ("user__username", "user__first_name", "user__last_name", "phone_number")
    autocomplete_fields = ("user",)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "member", "hub", "business_type", "status")
    list_filter = ("status", "business_type")
    search_fields = ("name", "registration_number", "member__user__username")
    autocomplete_fields = ("member",)