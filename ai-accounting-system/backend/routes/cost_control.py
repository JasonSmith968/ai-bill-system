"""AI Cost Control API endpoints."""

from flask import Blueprint, request, jsonify
from utils.jwt_helper import token_required, admin_required
from services.cost_control import get_cost_control, CostControlConfig

cost_control_bp = Blueprint("cost_control", __name__)


# --- User endpoints ---

@cost_control_bp.route("/my-usage", methods=["GET"])
@token_required
def my_usage(current_user):
    """Get current user's cost and usage for today."""
    svc = get_cost_control()
    plan = getattr(current_user, 'plan', 'free') or 'free'
    report = svc.get_user_cost_report(str(current_user.id), plan=plan)
    return jsonify(report)


@cost_control_bp.route("/my-check", methods=["POST"])
@token_required
def my_check(current_user):
    """Pre-request check: is this request within budget?"""
    data = request.get_json() or {}
    svc = get_cost_control()
    plan = getattr(current_user, 'plan', 'free') or 'free'
    allowed, details = svc.check_request_allowed(
        user_id=str(current_user.id),
        plan=plan,
        estimated_input_tokens=data.get('estimated_input_tokens', 0),
        estimated_output_tokens=data.get('estimated_output_tokens', 0),
        estimated_cost_cents=data.get('estimated_cost_cents', 0.0),
    )
    return jsonify(details), 200 if allowed else 429


# --- Admin endpoints ---

@cost_control_bp.route("/admin/dashboard", methods=["GET"])
@token_required
@admin_required
def admin_dashboard(current_user):
    """Global cost control dashboard."""
    svc = get_cost_control()
    return jsonify(svc.get_cost_dashboard())


@cost_control_bp.route("/admin/user/<user_id>", methods=["GET"])
@token_required
@admin_required
def admin_user_report(current_user, user_id):
    """Get cost report for a specific user."""
    plan = request.args.get("plan", "free")
    svc = get_cost_control()
    return jsonify(svc.get_user_cost_report(user_id, plan=plan))


@cost_control_bp.route("/admin/recommendations", methods=["GET"])
@token_required
@admin_required
def admin_recommendations(current_user):
    """Get cost optimization recommendations."""
    svc = get_cost_control()
    return jsonify({"recommendations": svc.get_optimization_recommendations()})


@cost_control_bp.route("/admin/anomaly", methods=["GET"])
@token_required
@admin_required
def admin_anomaly_check(current_user):
    """Check for global spending anomalies."""
    svc = get_cost_control()
    anomaly = svc.anomaly_detector.check_global_anomaly(svc.config)
    return jsonify({
        "has_anomaly": anomaly is not None,
        "anomaly": anomaly,
    })


@cost_control_bp.route("/admin/config", methods=["GET"])
@token_required
@admin_required
def admin_get_config(current_user):
    """Get current cost control configuration."""
    svc = get_cost_control()
    cfg = svc.config
    return jsonify({
        "free_tier": {
            "daily_requests": cfg.free_daily_requests,
            "daily_tokens": cfg.free_daily_tokens,
            "daily_cost_cents": cfg.free_daily_cost_cents,
            "monthly_cost_cents": cfg.free_monthly_cost_cents,
        },
        "starter_tier": {
            "daily_requests": cfg.starter_daily_requests,
            "daily_tokens": cfg.starter_daily_tokens,
            "daily_cost_cents": cfg.starter_daily_cost_cents,
            "monthly_cost_cents": cfg.starter_monthly_cost_cents,
        },
        "pro_tier": {
            "daily_requests": cfg.pro_daily_requests,
            "daily_tokens": cfg.pro_daily_tokens,
            "daily_cost_cents": cfg.pro_daily_cost_cents,
            "monthly_cost_cents": cfg.pro_monthly_cost_cents,
        },
        "enterprise_tier": {
            "daily_requests": cfg.enterprise_daily_requests,
            "daily_tokens": cfg.enterprise_daily_tokens,
            "daily_cost_cents": cfg.enterprise_daily_cost_cents,
            "monthly_cost_cents": cfg.enterprise_monthly_cost_cents,
        },
        "anomaly_spike_multiplier": cfg.anomaly_spike_multiplier,
        "gross_margin_alert_pct": cfg.gross_margin_alert_pct,
    })


@cost_control_bp.route("/admin/config", methods=["PUT"])
@token_required
@admin_required
def admin_update_config(current_user):
    """Update cost control configuration."""
    data = request.get_json() or {}
    svc = get_cost_control()
    cfg = svc.config

    tier_map = {
        'free': ('free_daily_requests', 'free_daily_tokens', 'free_daily_cost_cents', 'free_monthly_cost_cents'),
        'starter': ('starter_daily_requests', 'starter_daily_tokens', 'starter_daily_cost_cents', 'starter_monthly_cost_cents'),
        'pro': ('pro_daily_requests', 'pro_daily_tokens', 'pro_daily_cost_cents', 'pro_monthly_cost_cents'),
        'enterprise': ('enterprise_daily_requests', 'enterprise_daily_tokens', 'enterprise_daily_cost_cents', 'enterprise_monthly_cost_cents'),
    }

    updated = []
    for tier, keys in tier_map.items():
        tier_data = data.get(f'{tier}_tier', {})
        if tier_data:
            for key in keys:
                short = key.replace(f'{tier}_', '')
                if short in tier_data:
                    setattr(cfg, key, tier_data[short])
                    updated.append(key)

    if 'anomaly_spike_multiplier' in data:
        cfg.anomaly_spike_multiplier = float(data['anomaly_spike_multiplier'])
        updated.append('anomaly_spike_multiplier')

    if 'gross_margin_alert_pct' in data:
        cfg.gross_margin_alert_pct = float(data['gross_margin_alert_pct'])
        updated.append('gross_margin_alert_pct')

    return jsonify({"updated": updated})
