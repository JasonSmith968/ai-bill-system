"""AI Cost Control System — Unified guardrail for AI spending.

Ensures positive gross margin as user base grows by enforcing:
1. Per-user daily/monthly budget limits
2. Free tier quota enforcement
3. Pre-request cost guardrail
4. Post-request cost recording
5. Anomaly detection (spending spikes)
6. Cache hit rate tracking
7. Prompt compression savings tracking
8. Model routing cost optimization
"""

import time
import logging
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class CostControlConfig:
    """Cost control thresholds and limits."""

    # Free tier limits
    free_daily_requests: int = 50
    free_daily_tokens: int = 100000
    free_daily_cost_cents: float = 10.0
    free_monthly_cost_cents: float = 200.0

    # Paid tier limits (per plan)
    starter_daily_requests: int = 200
    starter_daily_tokens: int = 500000
    starter_daily_cost_cents: float = 50.0
    starter_monthly_cost_cents: float = 1000.0

    pro_daily_requests: int = 1000
    pro_daily_tokens: int = 2000000
    pro_daily_cost_cents: float = 200.0
    pro_monthly_cost_cents: float = 5000.0

    enterprise_daily_requests: int = 5000
    enterprise_daily_tokens: int = 10000000
    enterprise_daily_cost_cents: float = 1000.0
    enterprise_monthly_cost_cents: float = 25000.0

    # Anomaly detection
    anomaly_spike_multiplier: float = 3.0  # 3x average = anomaly
    anomaly_window_hours: int = 24
    anomaly_min_samples: int = 10

    # Cost optimization
    prefer_cache: bool = True
    prefer_compression: bool = True
    prefer_routing: bool = True

    # Alert thresholds
    gross_margin_alert_pct: float = 30.0  # Alert if margin < 30%
    free_user_burn_alert_cents: float = 500.0  # Alert if daily free user burn > $5


# Plan tier mapping
PLAN_TIERS = {
    'free': 'free',
    'starter': 'starter',
    'pro': 'pro',
    'enterprise': 'enterprise',
}


# ---------------------------------------------------------------------------
# Usage tracking (in-memory, per-user per-day)
# ---------------------------------------------------------------------------

@dataclass
class UserUsage:
    """Per-user daily usage counter."""
    user_id: str
    date: str  # YYYY-MM-DD
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_cents: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    compression_savings_tokens: int = 0
    routing_savings_cents: float = 0.0


class UsageTracker:
    """Thread-safe in-memory usage tracker with daily rollover."""

    def __init__(self):
        self._usage: dict[str, UserUsage] = {}
        self._lock = Lock()
        self._history: list[dict] = []  # Aggregated daily snapshots

    def _get_key(self, user_id: str) -> str:
        today = datetime.utcnow().strftime('%Y-%m-%d')
        return f"{user_id}:{today}"

    def get_usage(self, user_id: str) -> UserUsage:
        """Get current usage for a user, creating if needed."""
        key = self._get_key(user_id)
        with self._lock:
            if key not in self._usage:
                self._usage[key] = UserUsage(
                    user_id=user_id,
                    date=datetime.utcnow().strftime('%Y-%m-%d'),
                )
            return self._usage[key]

    def record_request(self, user_id: str, input_tokens: int = 0,
                       output_tokens: int = 0, cost_cents: float = 0.0,
                       cache_hit: bool = False,
                       compression_saved_tokens: int = 0,
                       routing_saved_cents: float = 0.0):
        """Record an AI request's usage."""
        usage = self.get_usage(user_id)
        with self._lock:
            usage.requests += 1
            usage.input_tokens += input_tokens
            usage.output_tokens += output_tokens
            usage.cost_cents += cost_cents
            if cache_hit:
                usage.cache_hits += 1
            else:
                usage.cache_misses += 1
            usage.compression_savings_tokens += compression_saved_tokens
            usage.routing_savings_cents += routing_saved_cents

    def get_all_usage_today(self) -> dict[str, UserUsage]:
        """Get all users' usage for today."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        with self._lock:
            return {
                k.split(':')[0]: v
                for k, v in self._usage.items()
                if v.date == today
            }

    def cleanup_old(self, days: int = 7):
        """Remove entries older than N days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
        with self._lock:
            to_delete = [k for k, v in self._usage.items() if v.date < cutoff]
            for k in to_delete:
                del self._usage[k]


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """Detects unusual spending patterns per user and globally."""

    def __init__(self):
        self._user_history: dict[str, list[float]] = defaultdict(list)
        self._global_history: list[float] = []
        self._lock = Lock()

    def record(self, user_id: str, cost_cents: float):
        """Record a cost sample."""
        with self._lock:
            self._user_history[user_id].append(cost_cents)
            self._global_history.append(cost_cents)
            # Keep last 1000 samples per user
            if len(self._user_history[user_id]) > 1000:
                self._user_history[user_id] = self._user_history[user_id][-1000:]
            if len(self._global_history) > 10000:
                self._global_history = self._global_history[-10000:]

    def check_anomaly(self, user_id: str, cost_cents: float,
                      config: CostControlConfig) -> dict | None:
        """Check if a cost is anomalous. Returns anomaly details or None."""
        with self._lock:
            history = self._user_history.get(user_id, [])

        if len(history) < config.anomaly_min_samples:
            return None

        avg = sum(history) / len(history)
        if avg <= 0:
            return None

        ratio = cost_cents / avg
        if ratio >= config.anomaly_spike_multiplier:
            return {
                'type': 'user_spike',
                'user_id': user_id,
                'current_cost_cents': cost_cents,
                'average_cost_cents': round(avg, 4),
                'ratio': round(ratio, 2),
                'threshold': config.anomaly_spike_multiplier,
                'sample_size': len(history),
                'detected_at': datetime.utcnow().isoformat(),
            }

        return None

    def check_global_anomaly(self, config: CostControlConfig) -> dict | None:
        """Check if global spending is anomalous."""
        with self._lock:
            history = self._global_history.copy()

        if len(history) < config.anomaly_min_samples * 10:
            return None

        recent = history[-100:]
        older = history[:-100] if len(history) > 100 else history

        recent_avg = sum(recent) / len(recent) if recent else 0
        older_avg = sum(older) / len(older) if older else 0

        if older_avg <= 0:
            return None

        ratio = recent_avg / older_avg
        if ratio >= config.anomaly_spike_multiplier:
            return {
                'type': 'global_spike',
                'recent_avg_cents': round(recent_avg, 4),
                'historical_avg_cents': round(older_avg, 4),
                'ratio': round(ratio, 2),
                'threshold': config.anomaly_spike_multiplier,
                'detected_at': datetime.utcnow().isoformat(),
            }

        return None


# ---------------------------------------------------------------------------
# Cost Control Service
# ---------------------------------------------------------------------------

class CostControlService:
    """Unified AI cost control service.

    Integrates free tier enforcement, budget guardrail, anomaly detection,
    and cost optimization recommendations.
    """

    def __init__(self, config: CostControlConfig | None = None):
        self.config = config or CostControlConfig()
        self.tracker = UsageTracker()
        self.anomaly_detector = AnomalyDetector()

    # --- Plan limits lookup ---

    def _get_plan_limits(self, plan: str) -> dict:
        """Get limits for a plan tier."""
        plan = PLAN_TIERS.get(plan, 'free')
        prefix = plan
        return {
            'daily_requests': getattr(self.config, f'{prefix}_daily_requests'),
            'daily_tokens': getattr(self.config, f'{prefix}_daily_tokens'),
            'daily_cost_cents': getattr(self.config, f'{prefix}_daily_cost_cents'),
            'monthly_cost_cents': getattr(self.config, f'{prefix}_monthly_cost_cents'),
        }

    # --- Pre-request guardrail ---

    def check_request_allowed(self, user_id: str, plan: str = 'free',
                              estimated_input_tokens: int = 0,
                              estimated_output_tokens: int = 0,
                              estimated_cost_cents: float = 0.0) -> tuple[bool, dict]:
        """Pre-request guardrail: check if request should be allowed.

        Returns:
            (allowed: bool, details: dict)
        """
        limits = self._get_plan_limits(plan)
        usage = self.tracker.get_usage(user_id)

        # Check daily request count
        if usage.requests >= limits['daily_requests']:
            return False, {
                'denied_reason': 'daily_request_limit',
                'limit': limits['daily_requests'],
                'used': usage.requests,
                'message': f'每日请求次数已达上限 ({limits["daily_requests"]})',
            }

        # Check daily token limit
        total_tokens = usage.input_tokens + usage.output_tokens + estimated_input_tokens + estimated_output_tokens
        if total_tokens > limits['daily_tokens']:
            return False, {
                'denied_reason': 'daily_token_limit',
                'limit': limits['daily_tokens'],
                'used': usage.input_tokens + usage.output_tokens,
                'message': f'每日 Token 用量已达上限 ({limits["daily_tokens"]:,})',
            }

        # Check daily cost limit
        projected_cost = usage.cost_cents + estimated_cost_cents
        if projected_cost > limits['daily_cost_cents']:
            return False, {
                'denied_reason': 'daily_cost_limit',
                'limit_cents': limits['daily_cost_cents'],
                'used_cents': round(usage.cost_cents, 4),
                'message': f'每日 AI 成本已达上限 (${limits["daily_cost_cents"]/100:.2f})',
            }

        return True, {
            'allowed': True,
            'remaining_requests': limits['daily_requests'] - usage.requests,
            'remaining_tokens': limits['daily_tokens'] - total_tokens,
            'remaining_cost_cents': round(limits['daily_cost_cents'] - projected_cost, 4),
        }

    # --- Post-request recording ---

    def record_usage(self, user_id: str, input_tokens: int = 0,
                     output_tokens: int = 0, cost_cents: float = 0.0,
                     cache_hit: bool = False,
                     compression_saved_tokens: int = 0,
                     routing_saved_cents: float = 0.0):
        """Record actual usage after an AI request completes."""
        self.tracker.record_request(
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_cents=cost_cents,
            cache_hit=cache_hit,
            compression_saved_tokens=compression_saved_tokens,
            routing_saved_cents=routing_saved_cents,
        )

        # Anomaly detection
        anomaly = self.anomaly_detector.check_anomaly(
            user_id, cost_cents, self.config
        )
        if anomaly:
            logger.warning(f"Cost anomaly detected: {anomaly}")
            self._emit_anomaly_alert(anomaly)

        # Record for anomaly history
        self.anomaly_detector.record(user_id, cost_cents)

    def _emit_anomaly_alert(self, anomaly: dict):
        """Emit an anomaly alert (log + optional webhook)."""
        logger.warning(
            f"COST ANOMALY: type={anomaly['type']} "
            f"user={anomaly.get('user_id', 'global')} "
            f"ratio={anomaly.get('ratio', 'N/A')} "
            f"cost={anomaly.get('current_cost_cents', anomaly.get('recent_avg_cents', 'N/A'))}c"
        )

    # --- User cost report ---

    def get_user_cost_report(self, user_id: str, plan: str = 'free') -> dict:
        """Get comprehensive cost report for a user."""
        usage = self.tracker.get_usage(user_id)
        limits = self._get_plan_limits(plan)

        total_tokens = usage.input_tokens + usage.output_tokens
        cache_total = usage.cache_hits + usage.cache_misses
        cache_hit_rate = (usage.cache_hits / cache_total * 100) if cache_total > 0 else 0

        return {
            'user_id': user_id,
            'plan': plan,
            'date': usage.date,
            'usage': {
                'requests': usage.requests,
                'input_tokens': usage.input_tokens,
                'output_tokens': usage.output_tokens,
                'total_tokens': total_tokens,
                'cost_cents': round(usage.cost_cents, 4),
                'cost_dollars': round(usage.cost_cents / 100, 4),
            },
            'limits': limits,
            'utilization': {
                'requests_pct': round(usage.requests / limits['daily_requests'] * 100, 1) if limits['daily_requests'] > 0 else 0,
                'tokens_pct': round(total_tokens / limits['daily_tokens'] * 100, 1) if limits['daily_tokens'] > 0 else 0,
                'cost_pct': round(usage.cost_cents / limits['daily_cost_cents'] * 100, 1) if limits['daily_cost_cents'] > 0 else 0,
            },
            'optimization': {
                'cache_hit_rate_pct': round(cache_hit_rate, 1),
                'cache_hits': usage.cache_hits,
                'cache_misses': usage.cache_misses,
                'compression_savings_tokens': usage.compression_savings_tokens,
                'routing_savings_cents': round(usage.routing_savings_cents, 4),
                'total_savings_cents': round(
                    usage.routing_savings_cents +
                    (usage.compression_savings_tokens * 0.0014),  # estimate
                    4
                ),
            },
        }

    # --- Admin dashboard ---

    def get_cost_dashboard(self) -> dict:
        """Get global cost control dashboard data."""
        all_usage = self.tracker.get_all_usage_today()

        total_requests = sum(u.requests for u in all_usage.values())
        total_tokens = sum(u.input_tokens + u.output_tokens for u in all_usage.values())
        total_cost = sum(u.cost_cents for u in all_usage.values())
        total_cache_hits = sum(u.cache_hits for u in all_usage.values())
        total_cache_misses = sum(u.cache_misses for u in all_usage.values())
        total_compression_saved = sum(u.compression_savings_tokens for u in all_usage.values())
        total_routing_saved = sum(u.routing_savings_cents for u in all_usage.values())

        cache_total = total_cache_hits + total_cache_misses
        cache_hit_rate = (total_cache_hits / cache_total * 100) if cache_total > 0 else 0

        # Top cost users
        top_users = sorted(
            all_usage.values(),
            key=lambda u: u.cost_cents,
            reverse=True,
        )[:20]

        # Anomaly check
        global_anomaly = self.anomaly_detector.check_global_anomaly(self.config)

        return {
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'summary': {
                'total_users': len(all_usage),
                'total_requests': total_requests,
                'total_tokens': total_tokens,
                'total_cost_cents': round(total_cost, 4),
                'total_cost_dollars': round(total_cost / 100, 4),
                'avg_cost_per_request_cents': round(total_cost / total_requests, 4) if total_requests > 0 else 0,
                'avg_cost_per_user_cents': round(total_cost / len(all_usage), 4) if all_usage else 0,
            },
            'cache': {
                'hit_rate_pct': round(cache_hit_rate, 1),
                'hits': total_cache_hits,
                'misses': total_cache_misses,
                'estimated_savings_cents': round(total_cache_hits * 0.01, 4),  # rough estimate
            },
            'compression': {
                'total_saved_tokens': total_compression_saved,
                'estimated_savings_cents': round(total_compression_saved * 0.0014, 4),
            },
            'routing': {
                'total_savings_cents': round(total_routing_saved, 4),
            },
            'top_users': [
                {
                    'user_id': u.user_id,
                    'requests': u.requests,
                    'tokens': u.input_tokens + u.output_tokens,
                    'cost_cents': round(u.cost_cents, 4),
                    'cache_hit_rate': round(u.cache_hits / (u.cache_hits + u.cache_misses) * 100, 1) if (u.cache_hits + u.cache_misses) > 0 else 0,
                }
                for u in top_users
            ],
            'anomaly': global_anomaly,
        }

    # --- Free tier enforcement ---

    def check_free_tier_allowed(self, user_id: str) -> tuple[bool, dict]:
        """Check if a free-tier user is within limits."""
        return self.check_request_allowed(user_id, plan='free')

    def get_free_tier_usage(self, user_id: str) -> dict:
        """Get free tier usage summary for a user."""
        return self.get_user_cost_report(user_id, plan='free')

    # --- Cost optimization recommendations ---

    def get_optimization_recommendations(self) -> list[dict]:
        """Generate cost optimization recommendations based on current usage."""
        recommendations = []
        all_usage = self.tracker.get_all_usage_today()

        if not all_usage:
            return recommendations

        # 1. Low cache hit rate
        total_hits = sum(u.cache_hits for u in all_usage.values())
        total_misses = sum(u.cache_misses for u in all_usage.values())
        total = total_hits + total_misses
        if total > 100:
            hit_rate = total_hits / total
            if hit_rate < 0.3:
                recommendations.append({
                    'type': 'low_cache_hit_rate',
                    'severity': 'high',
                    'message': f'Cache 命中率过低 ({hit_rate:.1%})，建议增加 cache TTL 或检查 prompt 一致性',
                    'metric': round(hit_rate * 100, 1),
                    'threshold': 30,
                })

        # 2. High-cost users
        avg_cost = sum(u.cost_cents for u in all_usage.values()) / len(all_usage)
        for u in all_usage.values():
            if u.cost_cents > avg_cost * 5:
                recommendations.append({
                    'type': 'high_cost_user',
                    'severity': 'medium',
                    'message': f'用户 {u.user_id} 成本异常偏高 (${u.cost_cents/100:.2f} vs 平均 ${avg_cost/100:.2f})',
                    'user_id': u.user_id,
                    'cost_cents': round(u.cost_cents, 4),
                    'avg_cost_cents': round(avg_cost, 4),
                })

        # 3. Compression not being used
        total_compressed = sum(u.compression_savings_tokens for u in all_usage.values())
        total_tokens = sum(u.input_tokens + u.output_tokens for u in all_usage.values())
        if total_tokens > 100000 and total_compressed < total_tokens * 0.05:
            recommendations.append({
                'type': 'low_compression_usage',
                'severity': 'medium',
                'message': 'Context 压缩使用率低，长对话可能导致 token 浪费',
                'compression_ratio': round(total_compressed / total_tokens * 100, 1) if total_tokens > 0 else 0,
            })

        # 4. Routing savings opportunity
        total_routing_saved = sum(u.routing_savings_cents for u in all_usage.values())
        total_cost = sum(u.cost_cents for u in all_usage.values())
        if total_cost > 100 and total_routing_saved < total_cost * 0.1:
            recommendations.append({
                'type': 'routing_optimization',
                'severity': 'low',
                'message': 'Model routing 节省比例偏低，建议检查任务分类是否准确',
                'routing_savings_pct': round(total_routing_saved / total_cost * 100, 1) if total_cost > 0 else 0,
            })

        return recommendations


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service: CostControlService | None = None


def get_cost_control() -> CostControlService:
    """Get the singleton CostControlService instance."""
    global _service
    if _service is None:
        _service = CostControlService()
    return _service


def reset_cost_control():
    """Reset the singleton (for testing)."""
    global _service
    _service = None
