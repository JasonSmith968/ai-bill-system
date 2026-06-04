"""BI API — centralized analytics endpoints for the BI dashboard."""

import logging
from flask import Blueprint, request, jsonify
from utils.jwt_helper import token_required
from services import bi_service

logger = logging.getLogger(__name__)

bi_bp = Blueprint('bi', __name__)


@bi_bp.route('/overview', methods=['GET'])
@token_required
def get_overview():
    """Full BI summary — all sections in one call."""
    data = bi_service.generate_bi_summary(request.current_user.id)
    return jsonify(data)


@bi_bp.route('/trend', methods=['GET'])
@token_required
def get_trend():
    """Monthly trend with moving average and forecast."""
    months = min(int(request.args.get('months', 12)), 24)
    trend = bi_service.get_monthly_trend(request.current_user.id, months)
    forecast = bi_service.forecast_next_month(request.current_user.id)
    return jsonify({'trend': trend, 'forecast': forecast})


@bi_bp.route('/cash-flow', methods=['GET'])
@token_required
def get_cash_flow():
    """Cash flow analysis."""
    months = min(int(request.args.get('months', 6)), 12)
    data = bi_service.get_cash_flow(request.current_user.id, months)
    return jsonify(data)


@bi_bp.route('/anomalies', methods=['GET'])
@token_required
def get_anomalies():
    """Spending anomaly detection with heatmap data."""
    months = min(int(request.args.get('months', 3)), 6)
    data = bi_service.detect_spending_anomalies(request.current_user.id, months)
    return jsonify(data)


@bi_bp.route('/budget-risk', methods=['GET'])
@token_required
def get_budget_risk():
    """Budget utilization and risk assessment."""
    data = bi_service.get_budget_risk(request.current_user.id)
    return jsonify(data)


@bi_bp.route('/subscriptions', methods=['GET'])
@token_required
def get_subscriptions():
    """Subscription waste analysis."""
    data = bi_service.detect_subscription_waste(request.current_user.id)
    return jsonify(data)


@bi_bp.route('/health-score', methods=['GET'])
@token_required
def get_health_score():
    """Financial health composite score."""
    data = bi_service.get_financial_health(request.current_user.id)
    return jsonify(data)


@bi_bp.route('/forecast', methods=['POST'])
@token_required
def post_forecast():
    """Forecast next month's spending."""
    data = bi_service.forecast_next_month(request.current_user.id)
    return jsonify(data)


@bi_bp.route('/report/generate', methods=['POST'])
@token_required
def generate_report():
    """Trigger async report generation via Celery."""
    body = request.get_json() or {}
    report_type = body.get('report_type', 'monthly')
    params = body.get('params', {})

    from models.task_record import TaskRecord
    from extensions import db

    task_record = TaskRecord(
        user_id=request.current_user.id,
        task_type='report',
        status='pending',
    )
    db.session.add(task_record)
    db.session.commit()

    try:
        from tasks.report_tasks import generate_pdf_report
        result = generate_pdf_report.delay(
            request.current_user.id, report_type, params
        )
        task_record.task_id = result.id
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to dispatch report task: {e}")
        task_record.status = 'failed'
        task_record.error = str(e)
        db.session.commit()
        return jsonify({'error': '任务创建失败'}), 500

    return jsonify({'task_id': task_record.task_id, 'status': 'pending'})


@bi_bp.route('/report/status/<task_id>', methods=['GET'])
@token_required
def report_status(task_id):
    """Check report generation status."""
    from models.task_record import TaskRecord
    task = TaskRecord.query.filter_by(task_id=task_id, user_id=request.current_user.id).first()
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify({'task': task.to_dict()})
