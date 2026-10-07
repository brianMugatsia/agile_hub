from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "title", "read_at")
    list_filter = ("created_at", "read_at")
    search_fields = ("recipient__username", "title", "message")
    readonly_fields = ("created_at",)