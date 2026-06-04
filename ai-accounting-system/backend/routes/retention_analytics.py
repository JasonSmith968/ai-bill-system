"""Retention Analytics API endpoints."""

from flask import Blueprint, request, jsonify
from utils.jwt_helper import token_required, admin_required
from services import retention_analytics

retention_bp = Blueprint("retention_analytics", __name__)


@retention_bp.route("/dashboard", methods=["GET"])
@token_required
@admin_required
def dashboard(current_user):
    """Unified retention dashboard with all 6 dimensions."""
    days = request.args.get("period", 30, type=int)
    data = retention_analytics.get_retention_dashboard(days=days)
    return jsonify(data)


@retention_bp.route("/cohort", methods=["GET"])
@token_required
@admin_required
def cohort_analysis(current_user):
    """Monthly cohort retention matrix."""
    months = request.args.get("months", 12, type=int)
    data = retention_analytics.get_cohort_analysis(months=months)
    return jsonify(data)


@retention_bp.route("/churn", methods=["GET"])
@token_required
@admin_required
def churn_prediction(current_user):
    """Churn risk scoring for users."""
    limit = request.args.get("limit", 50, type=int)
    data = retention_analytics.get_churn_prediction(limit=limit)
    return jsonify(data)


@retention_bp.route("/features", methods=["GET"])
@token_required
@admin_required
def feature_adoption(current_user):
    """Feature adoption rates across active users."""
    days = request.args.get("period", 30, type=int)
    data = retention_analytics.get_feature_adoption(days=days)
    return jsonify(data)


@retention_bp.route("/onboarding", methods=["GET"])
@token_required
@admin_required
def onboarding_analytics(current_user):
    """Onboarding funnel completion rates."""
    data = retention_analytics.get_onboarding_analytics()
    return jsonify(data)


@retention_bp.route("/referral", methods=["GET"])
@token_required
@admin_required
def referral_analytics(current_user):
    """Referral funnel and viral coefficient."""
    days = request.args.get("period", 90, type=int)
    data = retention_analytics.get_referral_analytics(days=days)
    return jsonify(data)


@retention_bp.route("/ai-engagement", methods=["GET"])
@token_required
@admin_required
def ai_engagement(current_user):
    """AI engagement scoring and user distribution."""
    days = request.args.get("period", 30, type=int)
    data = retention_analytics.get_ai_engagement(days=days)
    return jsonify(data)
