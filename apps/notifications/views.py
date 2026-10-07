from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.core.generic import ScopedModelListView
from .services import mark_notification_read

from .models import Notification


class NotificationListView(ScopedModelListView):
    model = Notification
    template_name = "notifications/list.html"
    page_title = "Notifications"
    columns = (
        {"label": "When", "field": "created_at"},
        {"label": "Notification", "field": "title"},
        {"label": "Message", "field": "message"},
        {"label": "Read", "field": "read_at"},
    )
    search_fields = ("title", "message")

    def get_queryset(self):
        return super().get_queryset().filter(recipient=self.request.user)


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        mark_notification_read(notification_id=notification.pk, recipient=request.user)
        messages.success(request, "Notification marked as read.")
        return redirect("notifications:list")