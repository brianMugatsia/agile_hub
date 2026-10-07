from django.utils import timezone

from .models import Notification


def create_notification(*, recipient, title, message, target_url=""):
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        target_url=target_url,
    )


def mark_notification_read(*, notification_id, recipient):
    notification = Notification.objects.get(pk=notification_id, recipient=recipient)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification