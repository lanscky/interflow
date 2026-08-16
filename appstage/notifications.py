from .models import Notification
from django.db import transaction


def _queue_push(notification_id):
    try:
        from .tasks import send_push_notification
        send_push_notification.delay(notification_id)
    except Exception:
        # La notification interne reste disponible même si le broker est indisponible.
        return


def notify_user(user, notification_type, title, message, data=None, unique_key=None):
    notification, _ = Notification.objects.get_or_create(
        unique_key=unique_key,
        defaults={
            'recipient': user,
            'notification_type': notification_type,
            'title': title,
            'message': message,
            'data': data or {},
        },
    ) if unique_key else (Notification.objects.create(
        recipient=user,
        notification_type=notification_type,
        title=title,
        message=message,
        data=data or {},
    ), True)
    if _:
        transaction.on_commit(
            lambda: _queue_push(notification.id),
            robust=True,
        )
    return notification


def notify_company(company, notification_type, title, message, data=None, unique_key_prefix=None):
    notifications = []
    relations = company.companyuser_set.filter(is_active=True).select_related('user')
    for relation in relations:
        key = f"{unique_key_prefix}:user:{relation.user_id}" if unique_key_prefix else None
        notifications.append(notify_user(
            relation.user, notification_type, title, message, data, key,
        ))
    return notifications
