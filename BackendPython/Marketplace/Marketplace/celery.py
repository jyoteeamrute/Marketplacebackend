import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Marketplace.settings')

app = Celery('Marketplace')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()