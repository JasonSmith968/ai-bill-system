"""Audit logging service."""

import logging
from flask import request, g
from extensions import db
from models.audit_log import AuditLog

biz_logger = logging.getLogger('business')


def log_action(action, user_id=None, resource_type=None, resource_id=None, details=None):
    """Log an auditable action."""
    try:
        ip_address = request.remote_addr if request else None
        user_agent = request.headers.get('User-Agent', '')[:500] if request else ''
        request_id = g.get('request_id', '') if g else ''

        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )
        db.session.add(log)
        db.session.commit()

        biz_logger.info(f"AUDIT: {action} user={user_id} resource={resource_type}:{resource_id}")
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to write audit log: {e}")


def get_audit_logs(filters=None, page=1, per_page=50):
    """Query audit logs with optional filters."""
    query = AuditLog.query

    if filters:
        if filters.get('user_id'):
            query = query.filter_by(user_id=filters['user_id'])
        if filters.get('action'):
            query = query.filter(AuditLog.action.like(f"%{filters['action']}%"))
        if filters.get('resource_type'):
            query = query.filter_by(resource_type=filters['resource_type'])
        if filters.get('start_date'):
            query = query.filter(AuditLog.created_at >= filters['start_date'])
        if filters.get('end_date'):
            query = query.filter(AuditLog.created_at <= filters['end_date'])

    query = query.order_by(AuditLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        'logs': [log.to_dict() for log in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }
