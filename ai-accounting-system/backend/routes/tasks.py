"""Task management API — query, cancel, and monitor async tasks."""

import logging
from flask import Blueprint, request, jsonify
from utils.jwt_helper import token_required
from models.task_record import TaskRecord

logger = logging.getLogger(__name__)

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/', methods=['GET'])
@token_required
def list_tasks():
    """List tasks for the current user with optional filters.

    Query params: task_type, status, limit
    """
    task_type = request.args.get('task_type')
    status = request.args.get('status')
    limit = min(int(request.args.get('limit', 20)), 100)

    tasks = TaskRecord.get_user_tasks(
        user_id=request.current_user.id,
        task_type=task_type,
        status=status,
        limit=limit,
    )
    return jsonify({'tasks': [t.to_dict() for t in tasks]})


@tasks_bp.route('/<task_id>', methods=['GET'])
@token_required
def get_task(task_id):
    """Get a specific task with live Celery status."""
    task = TaskRecord.query.filter_by(task_id=task_id, user_id=request.current_user.id).first()
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    # Merge live Celery status
    data = task.to_dict()
    try:
        from celery_app import celery
        async_result = celery.AsyncResult(task_id)
        data['celery_state'] = async_result.state
        if async_result.state == 'PENDING':
            data['status'] = 'pending'
        elif async_result.state == 'STARTED':
            data['status'] = 'running'
    except Exception:
        pass

    return jsonify({'task': data})


@tasks_bp.route('/<task_id>/cancel', methods=['POST'])
@token_required
def cancel_task(task_id):
    """Cancel a running task."""
    task = TaskRecord.query.filter_by(task_id=task_id, user_id=request.current_user.id).first()
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    if task.status not in ('pending', 'running'):
        return jsonify({'error': '任务已完成，无法取消'}), 400

    try:
        from celery_app import celery
        celery.control.revoke(task_id, terminate=True)

        task.status = 'failed'
        task.error = '用户取消'
        from extensions import db
        db.session.commit()

        return jsonify({'message': '任务已取消'})
    except Exception as e:
        logger.error(f"Cancel task failed: {e}")
        return jsonify({'error': '取消失败'}), 500


@tasks_bp.route('/stats', methods=['GET'])
@token_required
def task_stats():
    """Get task statistics for the current user."""
    user_id = request.current_user.id

    from sqlalchemy import func
    from extensions import db

    stats = db.session.query(
        TaskRecord.task_type,
        TaskRecord.status,
        func.count(TaskRecord.id)
    ).filter_by(user_id=user_id).group_by(
        TaskRecord.task_type, TaskRecord.status
    ).all()

    result = {}
    for task_type, status, count in stats:
        if task_type not in result:
            result[task_type] = {}
        result[task_type][status] = count

    return jsonify({'stats': result})
