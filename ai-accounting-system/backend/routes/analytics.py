"""Cost Analytics API endpoints."""

from flask import Blueprint, request, jsonify
from utils.jwt_helper import token_required, admin_required
from services import cost_analytics

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/dashboard", methods=["GET"])
@token_required
@admin_required
def financial_dashboard():
    """Get complete financial analytics dashboard."""
    period = request.args.get("period", 30, type=int)
    data = cost_analytics.get_financial_dashboard(period)
    return jsonify(data)


@analytics_bp.route("/gross-margin", methods=["GET"])
@token_required
@admin_required
def gross_margin():
    """Get gross margin analysis."""
    period = request.args.get("period", 30, type=int)
    data = cost_analytics.get_gross_margin(period)
    return jsonify(data)


@analytics_bp.route("/revenue", methods=["GET"])
@token_required
@admin_required
def revenue():
    """Get revenue metrics (MRR, ARR, ARPU, LTV)."""
    period = request.args.get("period", 30, type=int)
    data = cost_analytics.get_revenue_metrics(period)
    return jsonify(data)


@analytics_bp.route("/cost/per-user", methods=["GET"])
@token_required
@admin_required
def per_user_cost():
    """Get per-user token cost breakdown."""
    period = request.args.get("period", 30, type=int)
    data = cost_analytics.get_per_user_cost(period)
    return jsonify(data)


@analytics_bp.route("/cost/per-feature", methods=["GET"])
@token_required
@admin_required
def per_feature_cost():
    """Get per-feature cost breakdown."""
    period = request.args.get("period", 30, type=int)
    data = cost_analytics.get_per_feature_cost(period)
    return jsonify(data)


@analytics_bp.route("/cost/models", methods=["GET"])
@token_required
@admin_required
def model_comparison():
    """Get model cost comparison."""
    period = request.args.get("period", 30, type=int)
    data = cost_analytics.get_model_comparison(period)
    return jsonify(data)


@analytics_bp.route("/cost/cache-savings", methods=["GET"])
@token_required
@admin_required
def cache_savings():
    """Get cache and compression savings analysis."""
    period = request.args.get("period", 30, type=int)
    data = cost_analytics.get_cache_savings(period)
    return jsonify(data)


@analytics_bp.route("/cost/free-user-burn", methods=["GET"])
@token_required
@admin_required
def free_user_burn():
    """Get free user burn rate analysis."""
    period = request.args.get("period", 30, type=int)
    data = cost_analytics.get_free_user_burn_rate(period)
    return jsonify(data)


@analytics_bp.route("/alerts", methods=["GET"])
@token_required
@admin_required
def cost_alerts():
    """Get cost anomaly alerts."""
    data = cost_analytics.check_cost_alerts()
    return jsonify({"alerts": data, "count": len(data)})
