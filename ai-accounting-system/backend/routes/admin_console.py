"""Production Admin Console — unified dashboard aggregating all admin sections.

Sections:
1. User management
2. Subscription management
3. AI usage overview
4. Token cost dashboard
5. Growth metrics
6. Stripe revenue
7. System health
8. Queue monitoring
9. Agent monitoring
"""

from flask import Blueprint, request, jsonify
from utils.jwt_helper import token_required, admin_required

admin_console_bp = Blueprint("admin_console", __name__)


# ---------------------------------------------------------------------------
# 1. User Management
# ---------------------------------------------------------------------------

@admin_console_bp.route("/users", methods=["GET"])
@token_required
@admin_required
def user_management(current_user):
    """User list with search, pagination, and role filtering."""
    from models.user import User
    from models.role import Role

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "")
    role = request.args.get("role", "")
    status = request.args.get("status", "")

    query = User.query

    if search:
        like = f"%{search}%"
        query = query.filter(
            (User.username.ilike(like)) | (User.email.ilike(like))
        )

    if role:
        role_obj = Role.query.filter_by(name=role).first()
        if role_obj:
            query = query.filter(User.role_id == role_obj.id)

    if status == "active":
        query = query.filter(User.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(User.is_active.is_(False))

    total = query.count()
    users = query.order_by(User.created_at.desc()) \
        .offset((page - 1) * per_page) \
        .limit(per_page) \
        .all()

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "role": u.role.name if u.role else None,
                "plan": getattr(u, "plan", "free"),
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": getattr(u, "last_login", None),
            }
            for u in users
        ],
    })


@admin_console_bp.route("/users/stats", methods=["GET"])
@token_required
@admin_required
def user_stats(current_user):
    """Quick user statistics."""
    from models.user import User
    from extensions import db
    from sqlalchemy import text
    from datetime import datetime, timedelta

    total = User.query.count()
    active = User.query.filter(User.is_active.is_(True)).count()
    admins = User.query.filter(User.is_admin.is_(True)).count()

    now = datetime.utcnow()
    new_today = User.query.filter(User.created_at >= now.replace(hour=0, minute=0, second=0)).count()
    new_week = User.query.filter(User.created_at >= now - timedelta(days=7)).count()
    new_month = User.query.filter(User.created_at >= now - timedelta(days=30)).count()

    # Active today (from login_history if available)
    try:
        active_today = db.session.execute(text(
            "SELECT COUNT(DISTINCT user_id) FROM login_history "
            "WHERE login_at >= CURDATE() AND success = 1"
        )).scalar() or 0
    except Exception:
        active_today = 0

    return jsonify({
        "total_users": total,
        "active_users": active,
        "admin_users": admins,
        "new_today": new_today,
        "new_this_week": new_week,
        "new_this_month": new_month,
        "active_today": active_today,
    })


# ---------------------------------------------------------------------------
# 2. Subscription Management
# ---------------------------------------------------------------------------

@admin_console_bp.route("/subscriptions", methods=["GET"])
@token_required
@admin_required
def subscription_overview(current_user):
    """Subscription distribution and MRR overview."""
    from services.cost_analytics import get_revenue_metrics
    from extensions import db
    from sqlalchemy import text

    # Plan distribution
    try:
        rows = db.session.execute(text("""
            SELECT COALESCE(plan, 'free') AS plan, COUNT(*) AS cnt
            FROM users
            GROUP BY plan
        """)).fetchall()
        plan_distribution = {row[0]: row[1] for row in rows}
    except Exception:
        plan_distribution = {}

    # Revenue metrics
    try:
        revenue = get_revenue_metrics(period_days=30)
    except Exception:
        revenue = {"mrr": 0, "arr": 0, "error": "unavailable"}

    return jsonify({
        "plan_distribution": plan_distribution,
        "revenue": revenue,
    })


# ---------------------------------------------------------------------------
# 3. AI Usage Overview
# ---------------------------------------------------------------------------

@admin_console_bp.route("/ai-usage", methods=["GET"])
@token_required
@admin_required
def ai_usage_overview(current_user):
    """AI usage overview from cost control dashboard."""
    from services.cost_control import get_cost_control

    try:
        cc = get_cost_control()
        dashboard = cc.get_cost_dashboard()
    except Exception as e:
        dashboard = {"error": str(e)}

    return jsonify(dashboard)


# ---------------------------------------------------------------------------
# 4. Token Cost Dashboard
# ---------------------------------------------------------------------------

@admin_console_bp.route("/token-cost", methods=["GET"])
@token_required
@admin_required
def token_cost_dashboard(current_user):
    """Financial dashboard with token costs and savings."""
    from services.cost_analytics import get_financial_dashboard

    period = request.args.get("period", 30, type=int)
    try:
        data = get_financial_dashboard(period_days=period)
    except Exception as e:
        data = {"error": str(e)}

    return jsonify(data)


@admin_console_bp.route("/cost-recommendations", methods=["GET"])
@token_required
@admin_required
def cost_recommendations(current_user):
    """AI cost optimization recommendations."""
    from services.cost_control import get_cost_control

    try:
        cc = get_cost_control()
        recs = cc.get_optimization_recommendations()
    except Exception as e:
        recs = [{"error": str(e)}]

    return jsonify({"recommendations": recs})


# ---------------------------------------------------------------------------
# 5. Growth Metrics
# ---------------------------------------------------------------------------

@admin_console_bp.route("/growth", methods=["GET"])
@token_required
@admin_required
def growth_metrics(current_user):
    """Growth analytics dashboard."""
    from services.growth_service import get_growth_dashboard

    period = request.args.get("period", 30, type=int)
    try:
        data = get_growth_dashboard(period_days=period)
    except Exception as e:
        data = {"error": str(e)}

    return jsonify(data)


# ---------------------------------------------------------------------------
# 6. Stripe Revenue
# ---------------------------------------------------------------------------

@admin_console_bp.route("/revenue", methods=["GET"])
@token_required
@admin_required
def stripe_revenue(current_user):
    """Stripe revenue metrics."""
    from services.cost_analytics import get_revenue_metrics

    period = request.args.get("period", 30, type=int)
    try:
        data = get_revenue_metrics(period_days=period)
    except Exception as e:
        data = {"error": str(e)}

    return jsonify(data)


# ---------------------------------------------------------------------------
# 7. System Health
# ---------------------------------------------------------------------------

@admin_console_bp.route("/health", methods=["GET"])
@token_required
@admin_required
def system_health(current_user):
    """Full system health check."""
    from services.system_health import get_system_health

    try:
        data = get_system_health()
    except Exception as e:
        data = {"overall": "unknown", "error": str(e)}

    return jsonify(data)


# ---------------------------------------------------------------------------
# 8. Queue Monitoring
# ---------------------------------------------------------------------------

@admin_console_bp.route("/queues", methods=["GET"])
@token_required
@admin_required
def queue_monitoring(current_user):
    """Queue and worker monitoring."""
    from services.queue_monitor import get_queue_monitor

    try:
        data = get_queue_monitor()
    except Exception as e:
        data = {"error": str(e)}

    return jsonify(data)


# ---------------------------------------------------------------------------
# 9. Agent Monitoring
# ---------------------------------------------------------------------------

@admin_console_bp.route("/agents", methods=["GET"])
@token_required
@admin_required
def agent_monitoring(current_user):
    """Agent performance monitoring dashboard."""
    from agents.monitoring import get_monitor

    period = request.args.get("period", "24h")
    try:
        monitor = get_monitor()
        data = monitor.get_dashboard_data(period=period)
    except Exception as e:
        data = {"error": str(e)}

    return jsonify(data)


# ---------------------------------------------------------------------------
# Unified Dashboard (all sections in one call)
# ---------------------------------------------------------------------------

@admin_console_bp.route("/overview", methods=["GET"])
@token_required
@admin_required
def full_overview(current_user):
    """Unified admin console overview — all 9 sections in one response."""
    from datetime import datetime

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "sections": {},
    }

    # 1. User stats
    try:
        from models.user import User
        from extensions import db
        from sqlalchemy import text

        total = User.query.count()
        active = User.query.filter(User.is_active.is_(True)).count()
        try:
            active_today = db.session.execute(text(
                "SELECT COUNT(DISTINCT user_id) FROM login_history "
                "WHERE login_at >= CURDATE() AND success = 1"
            )).scalar() or 0
        except Exception:
            active_today = 0

        result["sections"]["users"] = {
            "total": total,
            "active": active,
            "active_today": active_today,
        }
    except Exception as e:
        result["sections"]["users"] = {"error": str(e)}

    # 2. Subscriptions
    try:
        from services.cost_analytics import get_revenue_metrics
        result["sections"]["subscriptions"] = get_revenue_metrics(period_days=30)
    except Exception as e:
        result["sections"]["subscriptions"] = {"error": str(e)}

    # 3. AI usage
    try:
        from services.cost_control import get_cost_control
        result["sections"]["ai_usage"] = get_cost_control().get_cost_dashboard()
    except Exception as e:
        result["sections"]["ai_usage"] = {"error": str(e)}

    # 4. Token cost
    try:
        from services.cost_analytics import get_financial_dashboard
        result["sections"]["token_cost"] = get_financial_dashboard(period_days=30)
    except Exception as e:
        result["sections"]["token_cost"] = {"error": str(e)}

    # 5. Growth
    try:
        from services.growth_service import get_growth_dashboard
        result["sections"]["growth"] = get_growth_dashboard(period_days=30)
    except Exception as e:
        result["sections"]["growth"] = {"error": str(e)}

    # 6. Revenue (same as subscriptions for overview)
    result["sections"]["revenue"] = result["sections"]["subscriptions"]

    # 7. System health
    try:
        from services.system_health import get_system_health
        result["sections"]["system_health"] = get_system_health()
    except Exception as e:
        result["sections"]["system_health"] = {"error": str(e)}

    # 8. Queues
    try:
        from services.queue_monitor import get_queue_monitor
        result["sections"]["queues"] = get_queue_monitor()
    except Exception as e:
        result["sections"]["queues"] = {"error": str(e)}

    # 9. Agents
    try:
        from agents.monitoring import get_monitor
        result["sections"]["agents"] = get_monitor().get_dashboard_data(period="24h")
    except Exception as e:
        result["sections"]["agents"] = {"error": str(e)}

    return jsonify(result)
