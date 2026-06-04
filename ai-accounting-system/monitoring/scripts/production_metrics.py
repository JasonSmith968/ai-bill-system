#!/usr/bin/env python3
"""
Production Metrics Collector

Collects metrics from the AI Accounting System for monitoring dashboards
and daily reports. Runs as a standalone script or can be imported.

Usage:
    python monitoring/scripts/production_metrics.py --output json
    python monitoring/scripts/production_metrics.py --output report --period 7d
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


def get_app():
    """Create Flask app context for database access."""
    from app import create_app
    return create_app("production")


def parse_period(period_str):
    """Parse period string like '1d', '7d', '30d' to timedelta."""
    unit = period_str[-1]
    value = int(period_str[:-1])
    if unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    return timedelta(days=1)


# ==============================================================================
# AI Cost Metrics
# ==============================================================================


def collect_ai_cost_metrics(period):
    """Collect AI/LLM cost and usage metrics."""
    from models.agent_log import AgentExecutionLog
    from models.usage import AIUsage
    from extensions import db
    from sqlalchemy import func

    since = datetime.utcnow() - period

    # Token consumption by model
    token_by_model = (
        db.session.query(
            AgentExecutionLog.model,
            func.sum(AgentExecutionLog.input_tokens).label("input_tokens"),
            func.sum(AgentExecutionLog.output_tokens).label("output_tokens"),
            func.sum(AgentExecutionLog.cost_cents).label("total_cost_cents"),
            func.count().label("call_count"),
        )
        .filter(AgentExecutionLog.created_at >= since)
        .group_by(AgentExecutionLog.model)
        .all()
    )

    # Per-user cost
    user_costs = (
        db.session.query(
            AgentExecutionLog.user_id,
            func.sum(AgentExecutionLog.cost_cents).label("total_cost"),
            func.sum(AgentExecutionLog.input_tokens + AgentExecutionLog.output_tokens).label(
                "total_tokens"
            ),
            func.count().label("request_count"),
        )
        .filter(AgentExecutionLog.created_at >= since, AgentExecutionLog.user_id.isnot(None))
        .group_by(AgentExecutionLog.user_id)
        .order_by(func.sum(AgentExecutionLog.cost_cents).desc())
        .limit(20)
        .all()
    )

    # Per-agent breakdown
    agent_stats = (
        db.session.query(
            AgentExecutionLog.agent_name,
            func.count().label("calls"),
            func.sum(AgentExecutionLog.cost_cents).label("cost"),
            func.avg(AgentExecutionLog.duration_ms).label("avg_latency"),
            func.sum(
                func.cast(AgentExecutionLog.success, db.Integer)
            ).label("success_count"),
        )
        .filter(AgentExecutionLog.created_at >= since)
        .group_by(AgentExecutionLog.agent_name)
        .all()
    )

    # Daily cost trend
    daily_costs = (
        db.session.query(
            func.date(AgentExecutionLog.created_at).label("date"),
            func.sum(AgentExecutionLog.cost_cents).label("cost"),
            func.count().label("calls"),
        )
        .filter(AgentExecutionLog.created_at >= since)
        .group_by(func.date(AgentExecutionLog.created_at))
        .order_by(func.date(AgentExecutionLog.created_at))
        .all()
    )

    # Global AI usage tracking
    global_usage = (
        db.session.query(
            func.sum(AIUsage.total_cost_cents).label("total_cost"),
            func.sum(AIUsage.total_requests).label("total_requests"),
            func.count(func.distinct(AIUsage.user_id)).label("unique_users"),
        )
        .filter(AIUsage.period_start >= since)
        .first()
    )

    return {
        "token_by_model": [
            {
                "model": r.model or "unknown",
                "input_tokens": int(r.input_tokens or 0),
                "output_tokens": int(r.output_tokens or 0),
                "total_cost_cents": round(float(r.total_cost_cents or 0), 2),
                "call_count": r.call_count,
            }
            for r in token_by_model
        ],
        "top_users_by_cost": [
            {
                "user_id": r.user_id,
                "total_cost_cents": round(float(r.total_cost or 0), 2),
                "total_tokens": int(r.total_tokens or 0),
                "request_count": r.request_count,
            }
            for r in user_costs
        ],
        "agent_breakdown": [
            {
                "agent": r.agent_name,
                "calls": r.calls,
                "cost_cents": round(float(r.cost or 0), 2),
                "avg_latency_ms": round(float(r.avg_latency or 0), 1),
                "success_rate": round(
                    (int(r.success_count or 0) / max(r.calls, 1)) * 100, 1
                ),
            }
            for r in agent_stats
        ],
        "daily_trend": [
            {
                "date": str(r.date),
                "cost_cents": round(float(r.cost or 0), 2),
                "calls": r.calls,
            }
            for r in daily_costs
        ],
        "global_summary": {
            "total_cost_cents": round(float(global_usage.total_cost or 0), 2),
            "total_requests": int(global_usage.total_requests or 0),
            "unique_users": global_usage.unique_users or 0,
        },
    }


# ==============================================================================
# System Stability Metrics
# ==============================================================================


def collect_system_metrics():
    """Collect system stability metrics from Docker and host."""
    import subprocess

    metrics = {"containers": {}, "host": {}, "redis": {}, "celery": {}}

    # Docker container stats
    try:
        result = subprocess.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                '{"name":"{{.Name}}","cpu":"{{.CPUPerc}}","mem":"{{.MemUsage}}","mem_pct":"{{.MemPerc}}","net":"{{.NetIO}}","pids":"{{.PIDs}}"}',
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        for line in result.stdout.strip().split("\n"):
            if line:
                stats = json.loads(line)
                metrics["containers"][stats["name"]] = {
                    "cpu_percent": stats["cpu"],
                    "memory_usage": stats["mem"],
                    "memory_percent": stats["mem_pct"],
                    "network_io": stats["net"],
                    "pids": int(stats["pids"]),
                }
    except Exception as e:
        metrics["containers_error"] = str(e)

    # Host metrics
    try:
        # Memory
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    mem[key] = int(val)
            total = mem.get("MemTotal", 1)
            available = mem.get("MemAvailable", 0)
            metrics["host"]["memory_total_mb"] = total // 1024
            metrics["host"]["memory_available_mb"] = available // 1024
            metrics["host"]["memory_used_percent"] = round(
                ((total - available) / total) * 100, 1
            )

        # CPU load
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            metrics["host"]["load_1m"] = float(parts[0])
            metrics["host"]["load_5m"] = float(parts[1])
            metrics["host"]["load_15m"] = float(parts[2])

        # Disk
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        metrics["host"]["disk_total_gb"] = round(total / (1024**3), 1)
        metrics["host"]["disk_free_gb"] = round(free / (1024**3), 1)
        metrics["host"]["disk_used_percent"] = round(
            ((total - free) / total) * 100, 1
        )
    except Exception as e:
        metrics["host_error"] = str(e)

    # Redis metrics
    try:
        result = subprocess.run(
            ["docker", "exec", "ai-redis", "redis-cli", "INFO", "memory"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("used_memory_human:"):
                metrics["redis"]["memory_used"] = line.split(":")[1].strip()
            elif line.startswith("used_memory_peak_human:"):
                metrics["redis"]["memory_peak"] = line.split(":")[1].strip()
            elif line.startswith("mem_fragmentation_ratio:"):
                metrics["redis"]["fragmentation_ratio"] = float(
                    line.split(":")[1].strip()
                )
    except Exception as e:
        metrics["redis_error"] = str(e)

    # Redis clients
    try:
        result = subprocess.run(
            ["docker", "exec", "ai-redis", "redis-cli", "INFO", "clients"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("connected_clients:"):
                metrics["redis"]["connected_clients"] = int(
                    line.split(":")[1].strip()
                )
    except Exception:
        pass

    # Celery queue lengths
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "ai-redis",
                "redis-cli",
                "LLEN",
                "celery",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        metrics["celery"]["default_queue_length"] = int(result.stdout.strip() or 0)

        for queue in ["ai", "ocr", "email", "report"]:
            result = subprocess.run(
                ["docker", "exec", "ai-redis", "redis-cli", "LLEN", queue],
                capture_output=True,
                text=True,
                timeout=10,
            )
            metrics["celery"][f"{queue}_queue_length"] = int(
                result.stdout.strip() or 0
            )
    except Exception as e:
        metrics["celery_error"] = str(e)

    return metrics


# ==============================================================================
# Stripe Metrics
# ==============================================================================


def collect_stripe_metrics(period):
    """Collect Stripe payment and subscription metrics."""
    from models.subscription import Subscription, Payment
    from models.processed_event import ProcessedEvent
    from extensions import db
    from sqlalchemy import func

    since = datetime.utcnow() - period

    # Subscription status distribution
    sub_distribution = (
        db.session.query(Subscription.status, func.count())
        .group_by(Subscription.status)
        .all()
    )

    # Payment success rate
    payment_stats = (
        db.session.query(
            func.count().label("total"),
            func.sum(func.cast(Payment.status == "succeeded", db.Integer)).label(
                "succeeded"
            ),
            func.sum(func.cast(Payment.status == "failed", db.Integer)).label("failed"),
            func.sum(Payment.amount).label("total_amount"),
        )
        .filter(Payment.created_at >= since)
        .first()
    )

    # Webhook processing
    webhook_stats = (
        db.session.query(
            func.count().label("total_events"),
            func.min(ProcessedEvent.created_at).label("first_event"),
            func.max(ProcessedEvent.created_at).label("last_event"),
        )
        .filter(ProcessedEvent.created_at >= since)
        .first()
    )

    # Daily revenue
    daily_revenue = (
        db.session.query(
            func.date(Payment.created_at).label("date"),
            func.sum(Payment.amount).label("revenue"),
            func.count().label("payment_count"),
        )
        .filter(Payment.created_at >= since, Payment.status == "succeeded")
        .group_by(func.date(Payment.created_at))
        .order_by(func.date(Payment.created_at))
        .all()
    )

    # Failed payments (need attention)
    failed_payments = (
        Payment.query.filter(
            Payment.created_at >= since, Payment.status == "failed"
        )
        .order_by(Payment.created_at.desc())
        .limit(10)
        .all()
    )

    # New vs churned subscriptions
    new_subs = Subscription.query.filter(Subscription.created_at >= since).count()
    churned = Subscription.query.filter(
        Subscription.canceled_at >= since
    ).count()

    return {
        "subscription_distribution": {r[0]: r[1] for r in sub_distribution},
        "payment_stats": {
            "total_payments": payment_stats.total or 0,
            "succeeded": int(payment_stats.succeeded or 0),
            "failed": int(payment_stats.failed or 0),
            "success_rate": round(
                (int(payment_stats.succeeded or 0) / max(payment_stats.total or 1, 1))
                * 100,
                1,
            ),
            "total_revenue_cents": round(float(payment_stats.total_amount or 0), 2),
        },
        "webhook_stats": {
            "total_events": webhook_stats.total_events or 0,
            "first_event": str(webhook_stats.first_event) if webhook_stats.first_event else None,
            "last_event": str(webhook_stats.last_event) if webhook_stats.last_event else None,
        },
        "daily_revenue": [
            {
                "date": str(r.date),
                "revenue_cents": round(float(r.revenue or 0), 2),
                "payment_count": r.payment_count,
            }
            for r in daily_revenue
        ],
        "failed_payments_recent": [
            {
                "id": p.id,
                "amount": float(p.amount or 0),
                "error": getattr(p, "failure_reason", None),
                "created_at": str(p.created_at),
            }
            for p in failed_payments
        ],
        "new_subscriptions": new_subs,
        "churned_subscriptions": churned,
    }


# ==============================================================================
# User Behavior Metrics
# ==============================================================================


def collect_user_metrics(period):
    """Collect user behavior and engagement metrics."""
    from models.user import User
    from models.login_history import LoginHistory
    from models.transaction import Transaction
    from models.agent_log import AgentExecutionLog
    from extensions import db
    from sqlalchemy import func

    since = datetime.utcnow() - period

    # Total users
    total_users = User.query.count()
    active_users = (
        db.session.query(func.count(func.distinct(LoginHistory.user_id)))
        .filter(LoginHistory.created_at >= since)
        .scalar()
    )

    # New registrations
    new_users = User.query.filter(User.created_at >= since).count()

    # DAU / WAU / MAU
    now = datetime.utcnow()
    dau = (
        db.session.query(func.count(func.distinct(LoginHistory.user_id)))
        .filter(LoginHistory.created_at >= now - timedelta(days=1))
        .scalar()
    )
    wau = (
        db.session.query(func.count(func.distinct(LoginHistory.user_id)))
        .filter(LoginHistory.created_at >= now - timedelta(days=7))
        .scalar()
    )
    mau = (
        db.session.query(func.count(func.distinct(LoginHistory.user_id)))
        .filter(LoginHistory.created_at >= now - timedelta(days=30))
        .scalar()
    )

    # Feature usage (transaction creation rate)
    txn_count = Transaction.query.filter(Transaction.created_at >= since).count()
    agent_count = AgentExecutionLog.query.filter(
        AgentExecutionLog.created_at >= since
    ).count()

    # Daily active users trend
    daily_active = (
        db.session.query(
            func.date(LoginHistory.created_at).label("date"),
            func.count(func.distinct(LoginHistory.user_id)).label("users"),
        )
        .filter(LoginHistory.created_at >= since)
        .group_by(func.date(LoginHistory.created_at))
        .order_by(func.date(LoginHistory.created_at))
        .all()
    )

    # Retention (users who logged in both this period and previous period)
    prev_since = since - period
    prev_active = set(
        r[0]
        for r in db.session.query(func.distinct(LoginHistory.user_id))
        .filter(LoginHistory.created_at >= prev_since, LoginHistory.created_at < since)
        .all()
    )
    current_active = set(
        r[0]
        for r in db.session.query(func.distinct(LoginHistory.user_id))
        .filter(LoginHistory.created_at >= since)
        .all()
    )
    retained = prev_active & current_active
    retention_rate = round((len(retained) / max(len(prev_active), 1)) * 100, 1)

    # Top features by usage
    feature_usage = {
        "transactions_created": txn_count,
        "ai_agent_calls": agent_count,
        "logins": LoginHistory.query.filter(LoginHistory.created_at >= since).count(),
    }

    return {
        "totals": {
            "total_users": total_users,
            "active_users_period": active_users,
            "new_registrations": new_users,
        },
        "engagement": {
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "dau_mau_ratio": round((dau / max(mau, 1)) * 100, 1),
        },
        "retention": {
            "retention_rate": retention_rate,
            "retained_users": len(retained),
            "previous_period_active": len(prev_active),
        },
        "feature_usage": feature_usage,
        "daily_active_trend": [
            {"date": str(r.date), "active_users": r.users} for r in daily_active
        ],
    }


# ==============================================================================
# Anomaly Detection
# ==============================================================================


def detect_anomalies(metrics):
    """Detect anomalies in collected metrics. Returns list of alerts."""
    alerts = []

    # --- AI Cost Anomalies ---
    ai = metrics.get("ai_cost", {})

    # High cost per user
    for user in ai.get("top_users_by_cost", [])[:5]:
        if user["total_cost_cents"] > 500:  # > $5 per period
            alerts.append(
                {
                    "severity": "warning",
                    "category": "ai_cost",
                    "message": f"User {user['user_id']} has high AI cost: ${user['total_cost_cents']/100:.2f}",
                    "metric": "user_cost",
                    "value": user["total_cost_cents"],
                    "threshold": 500,
                }
            )

    # Low success rate per agent
    for agent in ai.get("agent_breakdown", []):
        if agent["success_rate"] < 80 and agent["calls"] > 10:
            alerts.append(
                {
                    "severity": "warning",
                    "category": "ai_reliability",
                    "message": f"Agent '{agent['agent']}' has low success rate: {agent['success_rate']}%",
                    "metric": "agent_success_rate",
                    "value": agent["success_rate"],
                    "threshold": 80,
                }
            )

    # --- System Anomalies ---
    sys_metrics = metrics.get("system", {})
    host = sys_metrics.get("host", {})

    if host.get("memory_used_percent", 0) > 85:
        alerts.append(
            {
                "severity": "critical",
                "category": "system",
                "message": f"High memory usage: {host['memory_used_percent']}%",
                "metric": "memory_percent",
                "value": host["memory_used_percent"],
                "threshold": 85,
            }
        )

    if host.get("disk_used_percent", 0) > 85:
        alerts.append(
            {
                "severity": "critical",
                "category": "system",
                "message": f"High disk usage: {host['disk_used_percent']}%",
                "metric": "disk_percent",
                "value": host["disk_used_percent"],
                "threshold": 85,
            }
        )

    if host.get("load_1m", 0) > 4:
        alerts.append(
            {
                "severity": "warning",
                "category": "system",
                "message": f"High CPU load: {host['load_1m']}",
                "metric": "load_1m",
                "value": host["load_1m"],
                "threshold": 4,
            }
        )

    # Redis
    redis = sys_metrics.get("redis", {})
    frag = redis.get("fragmentation_ratio", 1.0)
    if frag > 1.5:
        alerts.append(
            {
                "severity": "warning",
                "category": "redis",
                "message": f"High Redis memory fragmentation: {frag}",
                "metric": "redis_fragmentation",
                "value": frag,
                "threshold": 1.5,
            }
        )

    # Celery queue backlog
    celery = sys_metrics.get("celery", {})
    for queue_name, length in celery.items():
        if isinstance(length, int) and length > 100:
            alerts.append(
                {
                    "severity": "warning",
                    "category": "celery",
                    "message": f"Celery queue '{queue_name}' backlog: {length}",
                    "metric": "queue_length",
                    "value": length,
                    "threshold": 100,
                }
            )

    # --- Stripe Anomalies ---
    stripe = metrics.get("stripe", {})

    success_rate = stripe.get("payment_stats", {}).get("success_rate", 100)
    if success_rate < 90 and stripe.get("payment_stats", {}).get("total_payments", 0) > 5:
        alerts.append(
            {
                "severity": "critical",
                "category": "stripe",
                "message": f"Low payment success rate: {success_rate}%",
                "metric": "payment_success_rate",
                "value": success_rate,
                "threshold": 90,
            }
        )

    # --- User Anomalies ---
    users = metrics.get("users", {})
    retention = users.get("retention", {}).get("retention_rate", 100)
    if retention < 50:
        alerts.append(
            {
                "severity": "warning",
                "category": "users",
                "message": f"Low user retention rate: {retention}%",
                "metric": "retention_rate",
                "value": retention,
                "threshold": 50,
            }
        )

    return alerts


# ==============================================================================
# Scaling Recommendations
# ==============================================================================


def generate_scaling_recommendations(metrics):
    """Generate scaling recommendations based on current metrics."""
    recommendations = []
    sys_metrics = metrics.get("system", {})
    host = sys_metrics.get("host", {})
    containers = sys_metrics.get("containers", {})
    celery = sys_metrics.get("celery", {})
    ai = metrics.get("ai_cost", {})

    # Memory
    mem_pct = host.get("memory_used_percent", 0)
    if mem_pct > 80:
        recommendations.append(
            {
                "component": "server",
                "action": "scale_up",
                "priority": "high",
                "reason": f"Memory usage at {mem_pct}%",
                "suggestion": "Upgrade to instance with more RAM, or add swap",
            }
        )

    # CPU
    load = host.get("load_1m", 0)
    if load > 2:
        recommendations.append(
            {
                "component": "server",
                "action": "scale_up",
                "priority": "medium",
                "reason": f"CPU load at {load}",
                "suggestion": "Upgrade to instance with more vCPUs",
            }
        )

    # Celery
    total_queue = sum(
        v for k, v in celery.items() if isinstance(v, int) and k.endswith("_queue_length")
    )
    if total_queue > 200:
        recommendations.append(
            {
                "component": "celery",
                "action": "scale_out",
                "priority": "high",
                "reason": f"Total queue backlog: {total_queue}",
                "suggestion": "Add more Celery worker containers",
            }
        )

    # Disk
    disk_pct = host.get("disk_used_percent", 0)
    if disk_pct > 75:
        recommendations.append(
            {
                "component": "storage",
                "action": "expand",
                "priority": "medium",
                "reason": f"Disk usage at {disk_pct}%",
                "suggestion": "Expand volume or add log rotation",
            }
        )

    # AI cost optimization
    ai_total = ai.get("global_summary", {}).get("total_cost_cents", 0)
    if ai_total > 1000:  # > $10
        recommendations.append(
            {
                "component": "ai_cost",
                "action": "optimize",
                "priority": "medium",
                "reason": f"AI cost at ${ai_total/100:.2f} for period",
                "suggestion": "Review token budgets, consider caching, check for unnecessary agent calls",
            }
        )

    # Container-specific
    for name, stats in containers.items():
        mem_str = stats.get("memory_percent", "0%").rstrip("%")
        try:
            mem = float(mem_str)
            if mem > 90:
                recommendations.append(
                    {
                        "component": name,
                        "action": "investigate",
                        "priority": "high",
                        "reason": f"Container memory at {mem}%",
                        "suggestion": f"Check {name} for memory leaks or increase limit",
                    }
                )
        except ValueError:
            pass

    # No issues
    if not recommendations:
        recommendations.append(
            {
                "component": "all",
                "action": "none",
                "priority": "info",
                "reason": "All metrics within normal range",
                "suggestion": "No scaling action needed",
            }
        )

    return recommendations


# ==============================================================================
# Report Generation
# ==============================================================================


def generate_daily_report(metrics, output_format="text"):
    """Generate a daily production report."""
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "period": "24h",
        "sections": {},
    }

    # AI Cost Summary
    ai = metrics.get("ai_cost", {})
    report["sections"]["ai_cost"] = {
        "total_cost_usd": round(ai.get("global_summary", {}).get("total_cost_cents", 0) / 100, 2),
        "total_requests": ai.get("global_summary", {}).get("total_requests", 0),
        "unique_users": ai.get("global_summary", {}).get("unique_users", 0),
        "top_agent": max(ai.get("agent_breakdown", []), key=lambda x: x["calls"], default={"agent": "N/A"}),
    }

    # System Health
    sys_m = metrics.get("system", {})
    report["sections"]["system_health"] = {
        "memory_used": sys_m.get("host", {}).get("memory_used_percent", "N/A"),
        "disk_used": sys_m.get("host", {}).get("disk_used_percent", "N/A"),
        "cpu_load": sys_m.get("host", {}).get("load_1m", "N/A"),
        "redis_memory": sys_m.get("redis", {}).get("memory_used", "N/A"),
        "total_queue_backlog": sum(
            v for k, v in sys_m.get("celery", {}).items()
            if isinstance(v, int) and k.endswith("_queue_length")
        ),
    }

    # Stripe
    stripe = metrics.get("stripe", {})
    report["sections"]["stripe"] = {
        "payments_processed": stripe.get("payment_stats", {}).get("total_payments", 0),
        "success_rate": stripe.get("payment_stats", {}).get("success_rate", 0),
        "revenue_usd": round(stripe.get("payment_stats", {}).get("total_revenue_cents", 0) / 100, 2),
        "new_subscriptions": stripe.get("new_subscriptions", 0),
        "churned": stripe.get("churned_subscriptions", 0),
    }

    # Users
    users = metrics.get("users", {})
    report["sections"]["users"] = {
        "dau": users.get("engagement", {}).get("dau", 0),
        "wau": users.get("engagement", {}).get("wau", 0),
        "mau": users.get("engagement", {}).get("mau", 0),
        "retention_rate": users.get("retention", {}).get("retention_rate", 0),
        "new_registrations": users.get("totals", {}).get("new_registrations", 0),
    }

    # Alerts & Recommendations
    report["alerts"] = metrics.get("alerts", [])
    report["recommendations"] = metrics.get("recommendations", [])

    if output_format == "json":
        return json.dumps(report, indent=2, ensure_ascii=False)

    # Text format
    lines = []
    lines.append("=" * 60)
    lines.append("  AI ACCOUNTING SYSTEM — DAILY PRODUCTION REPORT")
    lines.append(f"  Generated: {report['generated_at']}")
    lines.append("=" * 60)

    lines.append("\n--- AI COST ---")
    ai_s = report["sections"]["ai_cost"]
    lines.append(f"  Total Cost:     ${ai_s['total_cost_usd']:.2f}")
    lines.append(f"  Total Requests: {ai_s['total_requests']}")
    lines.append(f"  Unique Users:   {ai_s['unique_users']}")

    lines.append("\n--- SYSTEM HEALTH ---")
    sys_s = report["sections"]["system_health"]
    lines.append(f"  Memory:    {sys_s['memory_used']}%")
    lines.append(f"  Disk:      {sys_s['disk_used']}%")
    lines.append(f"  CPU Load:  {sys_s['cpu_load']}")
    lines.append(f"  Redis:     {sys_s['redis_memory']}")
    lines.append(f"  Queue:     {sys_s['total_queue_backlog']} pending")

    lines.append("\n--- STRIPE ---")
    st_s = report["sections"]["stripe"]
    lines.append(f"  Payments:  {st_s['payments_processed']} (success: {st_s['success_rate']}%)")
    lines.append(f"  Revenue:   ${st_s['revenue_usd']:.2f}")
    lines.append(f"  New Subs:  {st_s['new_subscriptions']}")
    lines.append(f"  Churned:   {st_s['churned']}")

    lines.append("\n--- USERS ---")
    u_s = report["sections"]["users"]
    lines.append(f"  DAU:       {u_s['dau']}")
    lines.append(f"  WAU:       {u_s['wau']}")
    lines.append(f"  MAU:       {u_s['mau']}")
    lines.append(f"  Retention: {u_s['retention_rate']}%")
    lines.append(f"  New:       {u_s['new_registrations']}")

    if report["alerts"]:
        lines.append(f"\n--- ALERTS ({len(report['alerts'])}) ---")
        for a in report["alerts"]:
            lines.append(f"  [{a['severity'].upper()}] {a['message']}")

    if report["recommendations"]:
        lines.append(f"\n--- SCALING RECOMMENDATIONS ({len(report['recommendations'])}) ---")
        for r in report["recommendations"]:
            lines.append(f"  [{r['priority'].upper()}] {r['component']}: {r['suggestion']}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


# ==============================================================================
# CLI Entry Point
# ==============================================================================


def collect_all(period_str="1d"):
    """Collect all metrics."""
    period = parse_period(period_str)

    with get_app().app_context():
        metrics = {
            "ai_cost": collect_ai_cost_metrics(period),
            "system": collect_system_metrics(),
            "stripe": collect_stripe_metrics(period),
            "users": collect_user_metrics(period),
        }

    metrics["alerts"] = detect_anomalies(metrics)
    metrics["recommendations"] = generate_scaling_recommendations(metrics)

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Production Metrics Collector")
    parser.add_argument(
        "--output",
        choices=["json", "report"],
        default="report",
        help="Output format",
    )
    parser.add_argument(
        "--period",
        default="1d",
        help="Collection period (e.g., 1d, 7d, 30d)",
    )
    parser.add_argument(
        "--save",
        help="Save report to file",
    )
    args = parser.parse_args()

    metrics = collect_all(args.period)

    if args.output == "json":
        output = json.dumps(metrics, indent=2, ensure_ascii=False, default=str)
    else:
        output = generate_daily_report(metrics, "text")

    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        with open(args.save, "w") as f:
            f.write(output)
        print(f"Report saved to {args.save}")
    else:
        print(output)


if __name__ == "__main__":
    main()
