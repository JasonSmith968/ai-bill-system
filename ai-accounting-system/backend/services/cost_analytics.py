"""
AI Cost Analytics Service

Real-time cost analysis for AI SaaS gross margin calculation.
Tracks per-user token cost, per-feature cost, model comparison,
cache savings, free user burn rate, and Stripe revenue.
"""

from datetime import datetime, date, timedelta
from collections import defaultdict
from extensions import db


# ==============================================================================
# Model Pricing (cents per 1K tokens)
# ==============================================================================

MODEL_PRICING = {
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-coder": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # OpenAI
    "gpt-4o": {"input": 250.0, "output": 1000.0},
    "gpt-4o-mini": {"input": 15.0, "output": 60.0},
    "gpt-3.5-turbo": {"input": 5.0, "output": 15.0},
    # Claude
    "claude-sonnet-4-20250514": {"input": 300.0, "output": 1500.0},
    "claude-haiku": {"input": 25.0, "output": 125.0},
    # Default fallback
    "default": {"input": 1.0, "output": 2.0},
}

# Feature cost multipliers (relative to base token cost)
FEATURE_MULTIPLIERS = {
    "ai_chat": 1.0,
    "ai_analysis": 1.2,
    "ai_report": 1.5,
    "ai_categorize": 0.5,
    "ocr": 0.8,
    "export": 0.1,
}

# Plan pricing (cents per month)
PLAN_PRICING = {
    "free": {"monthly": 0, "yearly": 0},
    "starter": {"monthly": 990, "yearly": 790},
    "pro": {"monthly": 2990, "yearly": 2390},
    "enterprise": {"monthly": 9990, "yearly": 7990},
}


def get_model_cost(model, input_tokens, output_tokens):
    """Calculate cost for a specific model call."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return round(input_cost + output_cost, 4)


# ==============================================================================
# Per-User Token Cost
# ==============================================================================


def get_per_user_cost(period_days=30):
    """Get per-user token cost breakdown."""
    from models.agent_log import AgentExecutionLog
    from models.user import User
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=period_days)

    rows = (
        db.session.query(
            AgentExecutionLog.user_id,
            func.sum(AgentExecutionLog.input_tokens).label("input_tokens"),
            func.sum(AgentExecutionLog.output_tokens).label("output_tokens"),
            func.sum(AgentExecutionLog.cost_cents).label("total_cost_cents"),
            func.count().label("request_count"),
            func.avg(AgentExecutionLog.duration_ms).label("avg_latency"),
        )
        .filter(AgentExecutionLog.created_at >= since, AgentExecutionLog.user_id.isnot(None))
        .group_by(AgentExecutionLog.user_id)
        .all()
    )

    users = []
    for r in rows:
        user = User.query.get(r.user_id)
        users.append({
            "user_id": r.user_id,
            "username": user.username if user else "unknown",
            "email": user.email if user else "unknown",
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "total_tokens": int((r.input_tokens or 0) + (r.output_tokens or 0)),
            "total_cost_cents": round(float(r.total_cost_cents or 0), 2),
            "total_cost_usd": round(float(r.total_cost_cents or 0) / 100, 4),
            "request_count": r.request_count,
            "avg_latency_ms": round(float(r.avg_latency or 0), 1),
            "cost_per_request": round(
                float(r.total_cost_cents or 0) / max(r.request_count, 1), 4
            ),
        })

    users.sort(key=lambda x: x["total_cost_cents"], reverse=True)

    return {
        "period_days": period_days,
        "total_users": len(users),
        "total_cost_usd": round(sum(u["total_cost_usd"] for u in users), 4),
        "avg_cost_per_user": round(
            sum(u["total_cost_usd"] for u in users) / max(len(users), 1), 4
        ),
        "users": users[:50],
    }


# ==============================================================================
# Per-Feature Call Cost
# ==============================================================================


def get_per_feature_cost(period_days=30):
    """Get per-feature cost breakdown by agent name."""
    from models.agent_log import AgentExecutionLog
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=period_days)

    rows = (
        db.session.query(
            AgentExecutionLog.agent_name,
            func.count().label("calls"),
            func.sum(AgentExecutionLog.input_tokens).label("input_tokens"),
            func.sum(AgentExecutionLog.output_tokens).label("output_tokens"),
            func.sum(AgentExecutionLog.cost_cents).label("total_cost"),
            func.avg(AgentExecutionLog.cost_cents).label("avg_cost"),
            func.avg(AgentExecutionLog.duration_ms).label("avg_latency"),
            func.sum(func.cast(AgentExecutionLog.success, db.Integer)).label("success_count"),
        )
        .filter(AgentExecutionLog.created_at >= since)
        .group_by(AgentExecutionLog.agent_name)
        .all()
    )

    features = []
    for r in rows:
        success_rate = round((int(r.success_count or 0) / max(r.calls, 1)) * 100, 1)
        features.append({
            "feature": r.agent_name,
            "calls": r.calls,
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "total_cost_cents": round(float(r.total_cost or 0), 2),
            "total_cost_usd": round(float(r.total_cost or 0) / 100, 4),
            "avg_cost_cents": round(float(r.avg_cost or 0), 4),
            "avg_latency_ms": round(float(r.avg_latency or 0), 1),
            "success_rate": success_rate,
            "cost_per_success": round(
                float(r.total_cost or 0) / max(int(r.success_count or 0), 1), 4
            ),
        })

    features.sort(key=lambda x: x["total_cost_cents"], reverse=True)

    return {
        "period_days": period_days,
        "total_features": len(features),
        "total_cost_usd": round(sum(f["total_cost_usd"] for f in features), 4),
        "features": features,
    }


# ==============================================================================
# Model Cost Comparison
# ==============================================================================


def get_model_comparison(period_days=30):
    """Compare costs across different models."""
    from models.agent_log import AgentExecutionLog
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=period_days)

    rows = (
        db.session.query(
            AgentExecutionLog.model,
            func.count().label("calls"),
            func.sum(AgentExecutionLog.input_tokens).label("input_tokens"),
            func.sum(AgentExecutionLog.output_tokens).label("output_tokens"),
            func.sum(AgentExecutionLog.cost_cents).label("total_cost"),
            func.avg(AgentExecutionLog.cost_cents).label("avg_cost"),
            func.avg(AgentExecutionLog.duration_ms).label("avg_latency"),
            func.sum(func.cast(AgentExecutionLog.success, db.Integer)).label("success_count"),
        )
        .filter(AgentExecutionLog.created_at >= since)
        .group_by(AgentExecutionLog.model)
        .all()
    )

    models = []
    for r in rows:
        model_name = r.model or "unknown"
        pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["default"])
        models.append({
            "model": model_name,
            "calls": r.calls,
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "total_cost_cents": round(float(r.total_cost or 0), 2),
            "total_cost_usd": round(float(r.total_cost or 0) / 100, 4),
            "avg_cost_cents": round(float(r.avg_cost or 0), 4),
            "avg_latency_ms": round(float(r.avg_latency or 0), 1),
            "success_rate": round(
                (int(r.success_count or 0) / max(r.calls, 1)) * 100, 1
            ),
            "pricing_input_per_1k": pricing["input"],
            "pricing_output_per_1k": pricing["output"],
            "cost_efficiency": round(
                float(r.total_cost or 0) / max(int(r.output_tokens or 1), 1) * 1000, 4
            ),
        })

    models.sort(key=lambda x: x["total_cost_cents"], reverse=True)

    return {
        "period_days": period_days,
        "models": models,
        "pricing_table": MODEL_PRICING,
    }


# ==============================================================================
# Cache Savings
# ==============================================================================


def get_cache_savings(period_days=30):
    """Estimate cache savings from prompt caching and context compression."""
    from models.agent_log import AgentExecutionLog
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=period_days)

    # Total actual cost
    total = (
        db.session.query(
            func.sum(AgentExecutionLog.cost_cents).label("total_cost"),
            func.sum(AgentExecutionLog.input_tokens).label("input_tokens"),
            func.sum(AgentExecutionLog.output_tokens).label("output_tokens"),
            func.count().label("calls"),
        )
        .filter(AgentExecutionLog.created_at >= since)
        .first()
    )

    actual_cost = float(total.total_cost or 0)
    actual_input = int(total.input_tokens or 0)
    actual_output = int(total.output_tokens or 0)
    total_calls = total.calls or 0

    # Estimate uncached cost (assume 40% of input tokens would be repeated)
    estimated_cache_hit_rate = 0.35  # 35% of input tokens cached
    cached_tokens = int(actual_input * estimated_cache_hit_rate)
    uncached_cost = actual_cost + (cached_tokens / 1000) * 0.14  # DeepSeek pricing

    # Context compression savings (assume 30% reduction)
    compression_rate = 0.30
    compression_savings = actual_input * compression_rate

    return {
        "period_days": period_days,
        "actual_cost_usd": round(actual_cost / 100, 4),
        "total_calls": total_calls,
        "total_input_tokens": actual_input,
        "total_output_tokens": actual_output,
        "cache": {
            "estimated_hit_rate": estimated_cache_hit_rate,
            "cached_tokens": cached_tokens,
            "estimated_savings_usd": round(
                (cached_tokens / 1000) * 0.14 / 100, 4
            ),
        },
        "compression": {
            "compression_rate": compression_rate,
            "tokens_saved": int(compression_savings),
            "estimated_savings_usd": round(
                (compression_savings / 1000) * 0.14 / 100, 4
            ),
        },
        "total_estimated_savings_usd": round(
            ((cached_tokens + compression_savings) / 1000) * 0.14 / 100, 4
        ),
        "effective_cost_usd": round(
            actual_cost / 100
            - ((cached_tokens + compression_savings) / 1000) * 0.14 / 100,
            4,
        ),
    }


# ==============================================================================
# Free User Burn Rate
# ==============================================================================


def get_free_user_burn_rate(period_days=30):
    """Analyze cost of free-tier users."""
    from models.agent_log import AgentExecutionLog
    from models.user import User
    from models.subscription import Subscription
    from models.plan import Plan
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=period_days)

    # Find free users (no active subscription or free plan)
    subscribed_user_ids = set(
        r[0]
        for r in db.session.query(Subscription.user_id)
        .filter(Subscription.status == "active")
        .all()
    )

    # Free user costs
    free_costs = (
        db.session.query(
            AgentExecutionLog.user_id,
            func.sum(AgentExecutionLog.cost_cents).label("cost"),
            func.sum(AgentExecutionLog.input_tokens + AgentExecutionLog.output_tokens).label(
                "tokens"
            ),
            func.count().label("calls"),
        )
        .filter(
            AgentExecutionLog.created_at >= since,
            AgentExecutionLog.user_id.isnot(None),
        )
        .group_by(AgentExecutionLog.user_id)
        .all()
    )

    free_users = []
    paid_users = []
    for r in free_costs:
        entry = {
            "user_id": r.user_id,
            "cost_cents": round(float(r.cost or 0), 2),
            "cost_usd": round(float(r.cost or 0) / 100, 4),
            "tokens": int(r.tokens or 0),
            "calls": r.calls,
        }
        if r.user_id in subscribed_user_ids:
            paid_users.append(entry)
        else:
            free_users.append(entry)

    free_users.sort(key=lambda x: x["cost_cents"], reverse=True)

    total_free_cost = sum(u["cost_usd"] for u in free_users)
    total_paid_cost = sum(u["cost_usd"] for u in paid_users)
    total_free_calls = sum(u["calls"] for u in free_users)
    total_paid_calls = sum(u["calls"] for u in paid_users)

    # Daily burn rate
    daily_burn = total_free_cost / max(period_days, 1)
    monthly_burn = daily_burn * 30

    # Conversion opportunity: free users with high usage
    high_usage_free = [
        u for u in free_users if u["cost_cents"] > 10  # > $0.10
    ]

    return {
        "period_days": period_days,
        "free_users": {
            "count": len(free_users),
            "total_cost_usd": round(total_free_cost, 4),
            "avg_cost_per_user": round(
                total_free_cost / max(len(free_users), 1), 4
            ),
            "total_calls": total_free_calls,
            "daily_burn_usd": round(daily_burn, 4),
            "monthly_burn_usd": round(monthly_burn, 4),
            "yearly_projection_usd": round(monthly_burn * 12, 4),
        },
        "paid_users": {
            "count": len(paid_users),
            "total_cost_usd": round(total_paid_cost, 4),
            "avg_cost_per_user": round(
                total_paid_cost / max(len(paid_users), 1), 4
            ),
            "total_calls": total_paid_calls,
        },
        "cost_ratio": round(
            total_free_cost / max(total_free_cost + total_paid_cost, 0.01) * 100, 1
        ),
        "high_usage_free_users": [
            {
                "user_id": u["user_id"],
                "cost_usd": u["cost_usd"],
                "calls": u["calls"],
                "conversion_priority": "high" if u["cost_cents"] > 50 else "medium",
            }
            for u in high_usage_free[:20]
        ],
    }


# ==============================================================================
# Stripe Revenue & MRR/ARR
# ==============================================================================


def get_revenue_metrics(period_days=30):
    """Get Stripe revenue metrics, MRR, and ARR."""
    from models.subscription import Subscription, Payment
    from models.plan import Plan
    from models.user import User
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=period_days)

    # Active subscriptions by plan
    active_subs = (
        db.session.query(
            Plan.name,
            Plan.price_monthly,
            Plan.price_yearly,
            func.count(Subscription.id).label("count"),
        )
        .join(Plan, Subscription.plan_id == Plan.id)
        .filter(Subscription.status == "active")
        .group_by(Plan.name, Plan.price_monthly, Plan.price_yearly)
        .all()
    )

    # Calculate MRR
    mrr_cents = 0
    plan_breakdown = []
    for r in active_subs:
        monthly_revenue = int(r.count) * int(r.price_monthly or 0)
        mrr_cents += monthly_revenue
        plan_breakdown.append({
            "plan": r.name,
            "subscribers": r.count,
            "monthly_price_cents": int(r.price_monthly or 0),
            "monthly_price_usd": round(int(r.price_monthly or 0) / 100, 2),
            "monthly_revenue_cents": monthly_revenue,
            "monthly_revenue_usd": round(monthly_revenue / 100, 2),
        })

    # Payment history
    payments = (
        db.session.query(
            func.count().label("total"),
            func.sum(func.cast(Payment.status == "succeeded", db.Integer)).label("succeeded"),
            func.sum(func.cast(Payment.status == "failed", db.Integer)).label("failed"),
            func.sum(Payment.amount).label("total_revenue"),
        )
        .filter(Payment.created_at >= since)
        .first()
    )

    # Daily revenue trend
    daily_revenue = (
        db.session.query(
            func.date(Payment.created_at).label("date"),
            func.sum(Payment.amount).label("revenue"),
            func.count().label("payments"),
        )
        .filter(Payment.created_at >= since, Payment.status == "succeeded")
        .group_by(func.date(Payment.created_at))
        .order_by(func.date(Payment.created_at))
        .all()
    )

    # New vs churned
    new_subs = Subscription.query.filter(Subscription.created_at >= since).count()
    churned = Subscription.query.filter(Subscription.canceled_at >= since).count()

    # Revenue per user (ARPU)
    total_active = sum(r.count for r in active_subs)
    arpu_cents = mrr_cents // max(total_active, 1)

    # Churn rate
    total_subs_start = total_active + churned
    churn_rate = round((churned / max(total_subs_start, 1)) * 100, 1)

    # LTV estimate (ARPU / churn rate * 100)
    ltv_cents = int(arpu_cents / max(churn_rate / 100, 0.01))

    return {
        "period_days": period_days,
        "mrr": {
            "cents": mrr_cents,
            "usd": round(mrr_cents / 100, 2),
        },
        "arr": {
            "cents": mrr_cents * 12,
            "usd": round(mrr_cents * 12 / 100, 2),
        },
        "arpu": {
            "cents": arpu_cents,
            "usd": round(arpu_cents / 100, 2),
        },
        "ltv": {
            "cents": ltv_cents,
            "usd": round(ltv_cents / 100, 2),
        },
        "active_subscribers": total_active,
        "new_subscriptions": new_subs,
        "churned_subscriptions": churned,
        "churn_rate_percent": churn_rate,
        "plan_breakdown": plan_breakdown,
        "payment_stats": {
            "total_payments": payments.total or 0,
            "succeeded": int(payments.succeeded or 0),
            "failed": int(payments.failed or 0),
            "success_rate": round(
                (int(payments.succeeded or 0) / max(payments.total or 1, 1)) * 100, 1
            ),
            "total_revenue_cents": round(float(payments.total_revenue or 0), 2),
            "total_revenue_usd": round(float(payments.total_revenue or 0) / 100, 2),
        },
        "daily_revenue": [
            {
                "date": str(r.date),
                "revenue_cents": round(float(r.revenue or 0), 2),
                "revenue_usd": round(float(r.revenue or 0) / 100, 2),
                "payments": r.payments,
            }
            for r in daily_revenue
        ],
    }


# ==============================================================================
# Gross Margin Calculation
# ==============================================================================


def get_gross_margin(period_days=30):
    """Calculate AI SaaS gross margin."""
    from models.agent_log import AgentExecutionLog
    from models.payment import Payment
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=period_days)

    # Revenue
    revenue = get_revenue_metrics(period_days)
    total_revenue_cents = revenue["payment_stats"]["total_revenue_cents"]

    # COGS (Cost of Goods Sold)
    # AI costs
    ai_costs = (
        db.session.query(func.sum(AgentExecutionLog.cost_cents))
        .filter(AgentExecutionLog.created_at >= since)
        .scalar()
    )
    ai_cost_cents = float(ai_costs or 0)

    # Infrastructure costs (estimated)
    # These would typically come from cloud billing APIs
    # For now, estimate based on container resource usage
    infra_cost_cents = _estimate_infra_cost(period_days)

    # Cache savings
    cache = get_cache_savings(period_days)
    savings_cents = cache["total_estimated_savings_usd"] * 100

    # Total COGS
    total_cogs_cents = ai_cost_cents + infra_cost_cents - savings_cents

    # Gross profit
    gross_profit_cents = total_revenue_cents - total_cogs_cents
    gross_margin_pct = round(
        (gross_profit_cents / max(total_revenue_cents, 1)) * 100, 1
    )

    # Cost breakdown
    cost_breakdown = {
        "ai_tokens": {
            "cents": round(ai_cost_cents, 2),
            "usd": round(ai_cost_cents / 100, 2),
            "pct_of_revenue": round(
                ai_cost_cents / max(total_revenue_cents, 1) * 100, 1
            ),
        },
        "infrastructure": {
            "cents": round(infra_cost_cents, 2),
            "usd": round(infra_cost_cents / 100, 2),
            "pct_of_revenue": round(
                infra_cost_cents / max(total_revenue_cents, 1) * 100, 1
            ),
        },
        "cache_savings": {
            "cents": round(savings_cents, 2),
            "usd": round(savings_cents / 100, 2),
        },
    }

    # Per-user economics
    burn = get_free_user_burn_rate(period_days)
    free_user_cost = burn["free_users"]["total_cost_usd"] * 100
    paid_user_revenue = total_revenue_cents

    return {
        "period_days": period_days,
        "revenue": {
            "total_cents": round(total_revenue_cents, 2),
            "total_usd": round(total_revenue_cents / 100, 2),
            "mrr_usd": revenue["mrr"]["usd"],
            "arr_usd": revenue["arr"]["usd"],
        },
        "cogs": {
            "total_cents": round(total_cogs_cents, 2),
            "total_usd": round(total_cogs_cents / 100, 2),
            "breakdown": cost_breakdown,
        },
        "gross_profit": {
            "cents": round(gross_profit_cents, 2),
            "usd": round(gross_profit_cents / 100, 2),
        },
        "gross_margin_percent": gross_margin_pct,
        "unit_economics": {
            "arpu_usd": revenue["arpu"]["usd"],
            "ltv_usd": revenue["ltv"]["usd"],
            "avg_ai_cost_per_user_usd": round(
                ai_cost_cents / 100 / max(revenue["active_subscribers"], 1), 4
            ),
            "free_user_burn_usd": burn["free_users"]["monthly_burn_usd"],
            "paid_user_revenue_usd": round(paid_user_revenue / 100, 2),
        },
        "benchmarks": {
            "target_gross_margin": 70,
            "current_vs_target": gross_margin_pct - 70,
            "ai_cost_ratio": round(
                ai_cost_cents / max(total_revenue_cents, 1) * 100, 1
            ),
            "industry_avg_ai_cost_ratio": 15,
        },
    }


def _estimate_infra_cost(period_days):
    """Estimate infrastructure cost based on container resources."""
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"],
            capture_output=True, text=True, timeout=10
        )

        total_cpu_hours = 0
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                cpu_str = parts[1].rstrip("%")
                try:
                    cpu_pct = float(cpu_str)
                    # Estimate cost: $0.04/vCPU/hour (typical cloud pricing)
                    total_cpu_hours += (cpu_pct / 100) * 24 * period_days
                except ValueError:
                    pass

        # $0.04/vCPU/hour + $0.01/GB RAM/hour (rough estimate)
        infra_cents = total_cpu_hours * 4  # 4 cents per vCPU-hour
        return round(infra_cents, 2)

    except Exception:
        # Fallback: estimate based on typical SaaS infra costs
        # ~$50/month for small deployment
        return round(50 * (period_days / 30) * 100, 2)


# ==============================================================================
# Cost Alerts
# ==============================================================================


def check_cost_alerts():
    """Check for cost anomalies and generate alerts."""
    alerts = []

    # Check free user burn rate
    burn = get_free_user_burn_rate(30)
    if burn["free_users"]["monthly_burn_usd"] > 50:
        alerts.append({
            "severity": "warning",
            "category": "free_user_burn",
            "message": f"Free user monthly burn: ${burn['free_users']['monthly_burn_usd']:.2f}",
            "metric": "monthly_burn",
            "value": burn["free_users"]["monthly_burn_usd"],
            "threshold": 50,
            "action": "Review free tier limits or upgrade high-usage free users",
        })

    # Check gross margin
    margin = get_gross_margin(30)
    if margin["gross_margin_percent"] < 50:
        alerts.append({
            "severity": "critical",
            "category": "gross_margin",
            "message": f"Gross margin below 50%: {margin['gross_margin_percent']}%",
            "metric": "gross_margin",
            "value": margin["gross_margin_percent"],
            "threshold": 50,
            "action": "Review pricing, reduce AI costs, or optimize token usage",
        })
    elif margin["gross_margin_percent"] < 70:
        alerts.append({
            "severity": "warning",
            "category": "gross_margin",
            "message": f"Gross margin below target 70%: {margin['gross_margin_percent']}%",
            "metric": "gross_margin",
            "value": margin["gross_margin_percent"],
            "threshold": 70,
            "action": "Consider optimizing AI token costs or adjusting pricing",
        })

    # Check per-user cost outliers
    users = get_per_user_cost(30)
    avg_cost = users["avg_cost_per_user"]
    for u in users["users"][:5]:
        if u["total_cost_usd"] > avg_cost * 10 and u["total_cost_usd"] > 1:
            alerts.append({
                "severity": "warning",
                "category": "user_cost_outlier",
                "message": f"User {u['username']} cost ${u['total_cost_usd']:.2f} (avg: ${avg_cost:.2f})",
                "metric": "user_cost",
                "value": u["total_cost_usd"],
                "threshold": avg_cost * 10,
                "action": "Review user's usage patterns, consider rate limiting",
            })

    # Check churn rate
    revenue = get_revenue_metrics(30)
    if revenue["churn_rate_percent"] > 10:
        alerts.append({
            "severity": "warning",
            "category": "churn",
            "message": f"High churn rate: {revenue['churn_rate_percent']}%",
            "metric": "churn_rate",
            "value": revenue["churn_rate_percent"],
            "threshold": 10,
            "action": "Investigate cancellation reasons, improve retention",
        })

    return alerts


# ==============================================================================
# Dashboard Data (all-in-one)
# ==============================================================================


def get_financial_dashboard(period_days=30):
    """Get complete financial dashboard data."""
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "period_days": period_days,
        "gross_margin": get_gross_margin(period_days),
        "revenue": get_revenue_metrics(period_days),
        "ai_costs": {
            "per_user": get_per_user_cost(period_days),
            "per_feature": get_per_feature_cost(period_days),
            "model_comparison": get_model_comparison(period_days),
        },
        "cache_savings": get_cache_savings(period_days),
        "free_user_burn": get_free_user_burn_rate(period_days),
        "cost_alerts": check_cost_alerts(),
    }
