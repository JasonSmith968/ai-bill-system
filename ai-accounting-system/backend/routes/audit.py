"""Audit log endpoints for administrators."""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from utils.jwt_helper import token_required
from security.rbac import require_permission
from security.audit import get_audit_logs

logger = logging.getLogger(__name__)

audit_bp = Blueprint('audit', __name__)


@audit_bp.route('/', methods=['GET'])
@token_required
@require_permission('audit:read')
def list_logs():
    """List audit logs with filters and pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)

    filters = {}
    if request.args.get('user_id'):
        filters['user_id'] = request.args.get('user_id', type=int)
    if request.args.get('action'):
        filters['action'] = request.args.get('action')
    if request.args.get('resource_type'):
        filters['resource_type'] = request.args.get('resource_type')
    if request.args.get('start_date'):
        try:
            filters['start_date'] = datetime.fromisoformat(request.args['start_date'])
        except ValueError:
            pass
    if request.args.get('end_date'):
        try:
            filters['end_date'] = datetime.fromisoformat(request.args['end_date'])
        except ValueError:
            pass

    result = get_audit_logs(filters=filters, page=page, per_page=per_page)
    return jsonify(result)


@audit_bp.route('/<int:log_id>', methods=['GET'])
@token_required
@require_permission('audit:read')
def get_log(log_id):
    """Get a single audit log entry."""
    from models.audit_log import AuditLog
    log = AuditLog.query.get(log_id)
    if not log:
        return jsonify({'error': '日志不存在'}), 404
    return jsonify({'log': log.to_dict()})
