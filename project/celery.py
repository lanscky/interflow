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


app.conf.beat_schedule = {
    'weekly-stage-report-reminders': {
        'task': 'appstage.tasks.create_weekly_stage_reminders',
        'schedule': crontab(minute=0, hour=8, day_of_week='monday'),
    },
}

#app.conf.timezone = 'Africa/Kinshasa'
