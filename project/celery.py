import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

app = Celery('project')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

# Activer django-celery-beat
from celery import platforms
platforms.C_FORCE_ROOT = True


# app.conf.beat_schedule = {
#     'activate-next-plan-every-midnight': {
#         'task': 'appstage.tasks.activate_next_plan',
#         'schedule': crontab(minute=0, hour=0),  # 00:00 tous les jours
#         'options': {'timezone': 'Africa/Kinshasa'},  # facultatif si TIMEZONE déjà configuré
#     },
# }

app.conf.timezone = 'Africa/Kinshasa'