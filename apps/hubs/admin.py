from django.contrib import admin

from .models import Hub, HubMembership


@admin.register(Hub)
class HubAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "region", "manager", "status")
    list_filter = ("status", "region")
    search_fields = ("code", "name", "region", "address")
    autocomplete_fields = ("manager",)


@admin.register(HubMembership)
class HubMembershipAdmin(admin.ModelAdmin):
    list_display = ("hub", "user", "title", "is_active", "joined_at")
    list_filter = ("is_active", "hub")
    search_fields = ("hub__name", "user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("hub", "user")