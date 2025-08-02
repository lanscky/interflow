from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.utils import timezone
from appstage.models import CompanySubscription
from datetime import timedelta

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
