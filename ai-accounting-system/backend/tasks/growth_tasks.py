"""Growth system Celery tasks — email lifecycle, retention checks, nudge triggers."""

import logging
from celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, queue='email', max_retries=3, soft_time_limit=60, time_limit=90,
             name='tasks.growth_tasks.send_email_task')
def send_email_task(self, user_id, template_name, context=None):
    """Send a lifecycle email using a registered template.

    Args:
        user_id: Recipient user ID
        template_name: EmailTemplate.name to render
        context: Extra template variables (optional)

    Returns:
        dict with 'email_log_id', 'status'
    """
    try:
        from services.growth_service import GrowthService
        from extensions import db

        service = GrowthService(db.session)
        result = service.send_lifecycle_email(user_id, template_name, context or {})
        return result

    except Exception as exc:
        logger.error(f"send_email_task failed for user={user_id} template={template_name}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery.task(bind=True, queue='email', max_retries=2, soft_time_limit=120, time_limit=150,
             name='tasks.growth_tasks.retention_check_task')
def retention_check_task(self):
    """Run periodic retention checks — identifies inactive users and sends re-engagement emails.

    Scheduled via Celery Beat (e.g., daily at 10:00 UTC).

    Returns:
        dict with 'inactive_3d', 'inactive_7d', 'emails_sent'
    """
    try:
        from services.growth_service import GrowthService
        from extensions import db

        service = GrowthService(db.session)
        result = service.run_retention_check()
        logger.info(f"Retention check completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"retention_check_task failed: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery.task(bind=True, queue='email', max_retries=2, soft_time_limit=120, time_limit=150,
             name='tasks.growth_tasks.nudge_check_task')
def nudge_check_task(self):
    """Run periodic nudge checks — evaluates nudge rules and sends eligible nudges.

    Scheduled via Celery Beat (e.g., every 6 hours).

    Returns:
        dict with 'rules_evaluated', 'nudges_sent', 'nudges_failed'
    """
    try:
        from services.growth_service import GrowthService
        from extensions import db

        service = GrowthService(db.session)
        result = service.run_nudge_check()
        logger.info(f"Nudge check completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"nudge_check_task failed: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery.task(bind=True, queue='email', max_retries=2, soft_time_limit=60, time_limit=90,
             name='tasks.growth_tasks.init_growth_defaults_task')
def init_growth_defaults_task(self):
    """Initialize default email templates, nudge rules, and onboarding flows.

    Called once during deployment or via admin endpoint.

    Returns:
        dict with counts of initialized items
    """
    try:
        from services.growth_service import GrowthService
        from extensions import db

        service = GrowthService(db.session)
        templates = service.init_email_templates()
        nudges = service.init_nudge_rules()

        result = {
            'email_templates': templates,
            'nudge_rules': nudges,
        }
        logger.info(f"Growth defaults initialized: {result}")
        return result

    except Exception as exc:
        logger.error(f"init_growth_defaults_task failed: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
