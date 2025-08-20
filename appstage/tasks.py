from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.utils import timezone
from appstage.models import CompanySubscription
from datetime import timedelta
from django.core.mail import send_mail

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