from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.utils import timezone
from appstage.models import AffectationStage, CompanySubscription, Notification, PushDevice, StageWeeklyReport
from appstage.notifications import notify_user
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
import requests

@shared_task
def activate_next_plan():
    print("Activation du prochain plan...")
    subs = CompanySubscription.objects.filter(next_plan__isnull=False, end_date__lte=timezone.now())
    for sub in subs:
        sub.plan = sub.next_plan
        sub.start_date = timezone.now()
        sub.end_date = timezone.now() + timedelta(days=sub.next_plan.duration_days)
        sub.nbre_offres = None if sub.next_plan.max_offres is None else sub.next_plan.max_offres
        sub.next_plan = None
        sub.change_effective_date = None
        sub.save()
        print(f"Plan mis à jour pour {sub.company.name} : {sub.plan.name} actif jusqu'au {sub.end_date}")

@shared_task
def send_welcome_email(user_email, username=None, plan_name=None,date_debut=None, date_fin=None):
    subject = "Bienvenue sur Totinda !"
    message = f"Merci de vous être inscrit, {username} !"
    if plan_name and date_debut and date_fin:
        message += f"\n\nVotre plan : {plan_name}\nDate de début : {date_debut}\nDate de fin : {date_fin}"
    sender = "noreply@totinda.com"  # Remplacez par votre adresse email d'envoi
    recipients = [user_email]

    send_mail(subject, message, sender, recipients)
    return f"Email envoyé à {user_email}"

@shared_task
def send_activation_email(email, username, activation_link):
    send_mail(
        subject="Activez votre compte",
        message=f"Bonjour {username}, cliquez sur ce lien pour activer votre compte : {activation_link}",
        from_email="noreply@totinda.com",
        recipient_list=[email],
    )


@shared_task
def create_weekly_stage_reminders():
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    stages = AffectationStage.objects.filter(
        status='in_progress',
    ).select_related('student__user', 'offre_stage')
    created = 0
    for stage in stages.iterator():
        if StageWeeklyReport.objects.filter(
            affectation=stage,
            week_start=week_start,
        ).exists():
            continue
        before = stage.student.user.notifications.count()
        notify_user(
            stage.student.user,
            'weekly_reminder',
            'Rapport hebdomadaire à compléter',
            f"Pensez à compléter votre rapport de la semaine pour le stage « {stage.offre_stage.title} ».",
            {'stage_id': stage.id, 'week_start': week_start.isoformat()},
            f"weekly-reminder:{stage.id}:{week_start.isoformat()}",
        )
        created += int(stage.student.user.notifications.count() > before)
    return created


@shared_task(autoretry_for=(requests.RequestException,), retry_backoff=True, max_retries=3)
def send_push_notification(notification_id):
    try:
        notification = Notification.objects.get(pk=notification_id)
    except Notification.DoesNotExist:
        return 0

    devices = list(PushDevice.objects.filter(
        user=notification.recipient,
        is_active=True,
    ))
    if not devices:
        return 0

    messages = [{
        'to': device.expo_push_token,
        'sound': 'default',
        'title': notification.title,
        'body': notification.message,
        'data': {
            **notification.data,
            'notification_id': notification.id,
            'notification_type': notification.notification_type,
        },
        'channelId': 'totinda-default',
    } for device in devices]
    response = requests.post(
        getattr(settings, 'EXPO_PUSH_URL', 'https://exp.host/--/api/v2/push/send'),
        json=messages,
        headers={
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/json',
        },
        timeout=10,
    )
    response.raise_for_status()
    tickets = response.json().get('data', [])
    sent = 0
    for device, ticket in zip(devices, tickets):
        if ticket.get('status') == 'ok':
            sent += 1
            if device.last_error:
                device.last_error = ''
                device.save(update_fields=['last_error'])
            continue
        details = ticket.get('details') or {}
        error = details.get('error') or ticket.get('message') or 'Erreur Expo Push'
        device.last_error = str(error)
        if error == 'DeviceNotRegistered':
            device.is_active = False
        device.save(update_fields=['last_error', 'is_active'])
    return sent
