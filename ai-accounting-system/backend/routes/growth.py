"""Growth system API endpoints — referral, affiliate, onboarding, nudges, admin dashboard."""

from flask import Blueprint, request, jsonify
from utils.jwt_helper import token_required, admin_required
from extensions import db
from services.growth_service import GrowthService

growth_bp = Blueprint("growth", __name__)


def _service():
    return GrowthService(db.session)


# ─── Referral ─────────────────────────────────────────────────────────────────

@growth_bp.route("/referral/code", methods=["GET"])
@token_required
def get_referral_code(current_user):
    """Get or generate the current user's referral code."""
    svc = _service()
    code = svc.generate_referral_code(current_user.id)
    return jsonify({"referral_code": code})


@growth_bp.route("/referral/stats", methods=["GET"])
@token_required
def referral_stats(current_user):
    """Get referral statistics for the current user."""
    svc = _service()
    stats = svc.get_referral_stats(current_user.id)
    return jsonify(stats)


@growth_bp.route("/referral/signup", methods=["POST"])
@token_required
def referral_signup(current_user):
    """Record a referral signup (called when a new user registers with a referral code)."""
    data = request.get_json()
    referral_code = data.get("referral_code")
    if not referral_code:
        return jsonify({"error": "referral_code required"}), 400

    svc = _service()
    result = svc.process_referral_signup(current_user.id, referral_code)
    return jsonify(result)


@growth_bp.route("/referral/convert", methods=["POST"])
@token_required
def referral_convert(current_user):
    """Mark a referral as converted (called on first payment)."""
    svc = _service()
    result = svc.process_referral_conversion(current_user.id)
    return jsonify(result)


# ─── Affiliate ────────────────────────────────────────────────────────────────

@growth_bp.route("/affiliate/track", methods=["POST"])
def affiliate_track():
    """Track an affiliate click (public endpoint — no auth required)."""
    data = request.get_json()
    affiliate_code = data.get("affiliate_code")
    if not affiliate_code:
        return jsonify({"error": "affiliate_code required"}), 400

    svc = _service()
    result = svc.track_affiliate_click(
        affiliate_code,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", ""),
        referrer_url=request.headers.get("Referer", ""),
        landing_page=data.get("landing_page"),
    )
    return jsonify(result)


@growth_bp.route("/affiliate/stats", methods=["GET"])
@token_required
def affiliate_stats(current_user):
    """Get affiliate statistics for the current user."""
    svc = _service()
    stats = svc.get_affiliate_stats(current_user.id)
    if stats is None:
        return jsonify({"error": "No affiliate profile found"}), 404
    return jsonify(stats)


@growth_bp.route("/affiliate/convert", methods=["POST"])
@token_required
@admin_required
def affiliate_convert(current_user):
    """Process an affiliate conversion (admin only)."""
    data = request.get_json()
    user_id = data.get("user_id")
    affiliate_code = data.get("affiliate_code")
    revenue_cents = data.get("revenue_cents", 0)

    if not user_id or not affiliate_code:
        return jsonify({"error": "user_id and affiliate_code required"}), 400

    svc = _service()
    result = svc.process_affiliate_conversion(user_id, affiliate_code, revenue_cents)
    return jsonify(result)


# ─── Onboarding ───────────────────────────────────────────────────────────────

@growth_bp.route("/onboarding/progress", methods=["GET"])
@token_required
def onboarding_progress(current_user):
    """Get onboarding progress for the current user."""
    svc = _service()
    progress = svc.get_onboarding_progress(current_user.id)
    return jsonify({"steps": progress})


@growth_bp.route("/onboarding/complete", methods=["POST"])
@token_required
def complete_onboarding_step(current_user):
    """Mark an onboarding step as completed or skipped."""
    data = request.get_json()
    step_key = data.get("step_key")
    status = data.get("status", "completed")

    if not step_key:
        return jsonify({"error": "step_key required"}), 400
    if status not in ("completed", "skipped"):
        return jsonify({"error": "status must be 'completed' or 'skipped'"}), 400

    svc = _service()
    result = svc.complete_onboarding_step(current_user.id, step_key, status)
    return jsonify(result)


# ─── Nudges ───────────────────────────────────────────────────────────────────

@growth_bp.route("/nudges/active", methods=["GET"])
@token_required
def active_nudges(current_user):
    """Get active nudges for the current user."""
    svc = _service()
    nudges = svc.check_nudges(current_user.id)
    return jsonify({"nudges": nudges})


# ─── Growth Admin Dashboard ──────────────────────────────────────────────────

@growth_bp.route("/admin/dashboard", methods=["GET"])
@token_required
@admin_required
def growth_dashboard(current_user):
    """Get growth analytics dashboard (admin only)."""
    period = request.args.get("period", 30, type=int)
    svc = _service()
    dashboard = svc.get_growth_dashboard(period)
    return jsonify(dashboard)


@growth_bp.route("/admin/init", methods=["POST"])
@token_required
@admin_required
def init_growth_defaults(current_user):
    """Initialize default email templates, nudge rules (admin only)."""
    svc = _service()
    templates = svc.init_email_templates()
    nudges = svc.init_nudge_rules()
    return jsonify({
        "email_templates": templates,
        "nudge_rules": nudges,
    })


@growth_bp.route("/admin/retention/run", methods=["POST"])
@token_required
@admin_required
def run_retention(current_user):
    """Manually trigger retention check (admin only)."""
    svc = _service()
    result = svc.run_retention_check()
    return jsonify(result)


@growth_bp.route("/admin/nudges/run", methods=["POST"])
@token_required
@admin_required
def run_nudges(current_user):
    """Manually trigger nudge check (admin only)."""
    svc = _service()
    result = svc.run_nudge_check()
    return jsonify(result)
