"""Celery tasks for PDF/Excel report generation."""

import os
import logging
from celery_app import celery

logger = logging.getLogger(__name__)


def _update_task_record(task_id, status, result=None, error=None):
    """Update the TaskRecord in DB."""
    from models.task_record import TaskRecord
    from extensions import db
    from datetime import datetime

    record = TaskRecord.query.filter_by(task_id=task_id).first()
    if not record:
        return
    record.status = status
    if status == 'running':
        record.started_at = datetime.utcnow()
    elif status in ('success', 'failed'):
        record.completed_at = datetime.utcnow()
    if result is not None:
        record.result = result
    if error is not None:
        record.error = error
    db.session.commit()


@celery.task(bind=True, queue='report', max_retries=2, soft_time_limit=300, time_limit=360,
             name='tasks.report_tasks.generate_pdf_report')
def generate_pdf_report(self, user_id, report_type='monthly', params=None):
    """Generate a PDF report asynchronously.

    Args:
        user_id: Report owner
        report_type: 'weekly' | 'monthly' | 'custom'
        params: Additional parameters (year, month, etc.)

    Returns:
        dict with 'file_path', 'file_name', 'report_type'
    """
    _update_task_record(self.request.id, 'running')

    try:
        from services.bi_service import generate_bi_summary
        from services.report_generator import ReportGenerator
        from models.user import User

        user = User.query.get(user_id)
        username = user.username if user else 'User'

        bi_data = generate_bi_summary(user_id)

        # Generate PDF
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'reports', str(user_id))
        os.makedirs(upload_dir, exist_ok=True)
        pdf_filename = f'{report_type}_report_{self.request.id[:8]}.pdf'
        pdf_path = os.path.join(upload_dir, pdf_filename)

        generator = ReportGenerator(user_id, bi_data, username)
        generator.generate_pdf(report_type, pdf_path)

        # Generate Excel
        xlsx_filename = f'{report_type}_report_{self.request.id[:8]}.xlsx'
        xlsx_path = os.path.join(upload_dir, xlsx_filename)
        generator.generate_enhanced_excel(xlsx_path)

        output = {
            'pdf_path': f'reports/{user_id}/{pdf_filename}',
            'pdf_name': pdf_filename,
            'xlsx_path': f'reports/{user_id}/{xlsx_filename}',
            'xlsx_name': xlsx_filename,
            'report_type': report_type,
        }

        _update_task_record(self.request.id, 'success', result=output)

        # Notify via WebSocket
        try:
            from websocket.events import emit_user_event
            emit_user_event(user_id, 'report_ready', {
                'task_id': self.request.id,
                'report_type': report_type,
                'pdf_name': pdf_filename,
            })
        except Exception as ws_err:
            logger.warning(f"WebSocket notification failed (non-fatal): {ws_err}")

        return output

    except Exception as exc:
        logger.error(f"generate_pdf_report failed: {exc}")
        _update_task_record(self.request.id, 'failed', error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery.task(bind=True, queue='report', max_retries=1, soft_time_limit=180, time_limit=210,
             name='tasks.report_tasks.generate_weekly_report')
def generate_weekly_report(self, user_id):
    """Generate weekly report for a single user."""
    return generate_pdf_report(user_id, 'weekly')


@celery.task(bind=True, queue='report', max_retries=1, soft_time_limit=180, time_limit=210,
             name='tasks.report_tasks.generate_monthly_report')
def generate_monthly_report(self, user_id):
    """Generate monthly report for a single user."""
    return generate_pdf_report(user_id, 'monthly')


@celery.task(bind=True, queue='report', max_retries=1, soft_time_limit=600, time_limit=660,
             name='tasks.report_tasks.generate_monthly_report_all')
def generate_monthly_report_all(self):
    """Generate monthly reports for all active users. Called by Celery Beat."""
    from models.user import User
    from models.transaction import Transaction
    from extensions import db
    from sqlalchemy import func
    from datetime import date, timedelta

    # Find users with transactions in the last month
    month_ago = date.today() - timedelta(days=30)
    active_user_ids = db.session.query(Transaction.user_id).filter(
        Transaction.date >= month_ago
    ).distinct().all()

    count = 0
    for (user_id,) in active_user_ids:
        try:
            generate_monthly_report.delay(user_id)
            count += 1
        except Exception as e:
            logger.error(f"Failed to dispatch monthly report for user {user_id}: {e}")

    logger.info(f"Dispatched {count} monthly report tasks")
    return {'dispatched': count}
