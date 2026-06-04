"""Celery application factory with priority queues and dead-letter support."""

import os
from celery import Celery
from celery.schedules import crontab

celery = Celery('ai_accounting')

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------
celery.conf.update(
    # Broker & result backend
    broker_url=os.environ.get('CELERY_BROKER_URL', os.environ.get('REDIS_URL', 'redis://localhost:6379/0')),
    result_backend=os.environ.get('CELERY_RESULT_BACKEND', os.environ.get('REDIS_URL', 'redis://localhost:6379/0')),

    # Serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],

    # Timezone
    timezone='Asia/Shanghai',
    enable_utc=True,

    # Results
    result_expires=3600,  # 1 hour

    # Reliability — dead-letter semantics
    task_reject_on_worker_lost=True,
    task_acks_late=True,

    # Priority (higher number = higher priority)
    task_queue_max_priority=10,

    # Task routing — each task type goes to its designated queue
    task_routes={
        'tasks.ai_tasks.*': {'queue': 'ai'},
        'tasks.ocr_tasks.*': {'queue': 'ocr'},
        'tasks.email_tasks.*': {'queue': 'email'},
        'tasks.report_tasks.*': {'queue': 'report'},
        'tasks.growth_tasks.*': {'queue': 'email'},
    },

    # Default queue
    task_default_queue='ai',
)

# ---------------------------------------------------------------------------
# Queue definitions with priority support
# ---------------------------------------------------------------------------
celery.conf.task_queues = {
    'ai':      {'exchange': 'ai',      'routing_key': 'ai',      'queue_arguments': {'x-max-priority': 10}},
    'ocr':     {'exchange': 'ocr',     'routing_key': 'ocr',     'queue_arguments': {'x-max-priority': 10}},
    'email':   {'exchange': 'email',   'routing_key': 'email',   'queue_arguments': {'x-max-priority': 10}},
    'report':  {'exchange': 'report',  'routing_key': 'report',  'queue_arguments': {'x-max-priority': 10}},
}

# ---------------------------------------------------------------------------
# Beat schedule (periodic tasks)
# ---------------------------------------------------------------------------
celery.conf.beat_schedule = {
    'cleanup-expired-tokens': {
        'task': 'tasks.email_tasks.cleanup_expired_tokens',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'generate-monthly-reports': {
        'task': 'tasks.report_tasks.generate_monthly_report_all',
        'schedule': crontab(hour=8, minute=0, day_of_month=1),  # 1st of month at 8 AM
    },
    'growth-retention-check': {
        'task': 'tasks.growth_tasks.retention_check_task',
        'schedule': crontab(hour=10, minute=0),  # Daily at 10 AM
    },
    'growth-nudge-check': {
        'task': 'tasks.growth_tasks.nudge_check_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
}


def make_celery(app=None):
    """Bind Celery to a Flask app context (call once during app factory)."""
    if app is not None:
        celery.conf.update(
            broker_url=app.config.get('CELERY_BROKER_URL', celery.conf.broker_url),
            result_backend=app.config.get('CELERY_RESULT_BACKEND', celery.conf.result_backend),
        )

        class ContextTask(celery.Task):
            """Wrap every task execution in a Flask app context."""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    return celery
