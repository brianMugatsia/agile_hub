from django.urls import path

from .views import MarkNotificationReadView, NotificationListView

app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="list"),
    path("<int:pk>/read/", MarkNotificationReadView.as_view(), name="mark_read"),
]