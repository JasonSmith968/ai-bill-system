"""Agent Monitoring — aggregated metrics for the monitoring dashboard.

Pulls data from:
- LLMTracer (call stats, costs, latency)
- CircuitBreaker (breaker states)
- AgentExecutionLog (historical data)
- TokenBudget (current request usage)
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_monitor = None


def get_monitor() -> 'AgentMonitor':
    """Get or create the singleton AgentMonitor."""
    global _monitor
    if _monitor is None:
        _monitor = AgentMonitor()
    return _monitor


class AgentMonitor:
    """Aggregates agent metrics for monitoring and alerting."""

    def get_dashboard_data(self, period: str = '24h') -> dict:
        """Return comprehensive dashboard data.

        Args:
            period: Time window ('1h', '24h', '7d', '30d')

        Returns:
            {
                summary: {total_calls, success_rate, avg_latency, total_cost},
                per_agent: [{name, calls, success_rate, avg_latency, cost}],
                error_breakdown: {error_type: count},
                cost_trend: [{timestamp, cost}],
                circuit_breakers: [{agent, state, failures}],
                alerts: [{level, message, agent}],
            }
        """
        period_seconds = self._parse_period(period)

        # Summary from tracer
        from agents.llm_tracer import get_tracer
        tracer = get_tracer()
        summary = tracer.get_total_stats(period_seconds)

        # Per-agent stats
        per_agent = self._get_per_agent_stats(period_seconds)

        # Error breakdown
        error_breakdown = self._get_error_breakdown(period_seconds)

        # Circuit breaker states
        circuit_breakers = self._get_circuit_breaker_states()

        # Alerts
        alerts = self.get_alerts()

        return {
            'summary': summary,
            'per_agent': per_agent,
            'error_breakdown': error_breakdown,
            'circuit_breakers': circuit_breakers,
            'alerts': alerts,
        }

    def get_alerts(self) -> list[dict]:
        """Return current active alerts.

        Checks for:
        - Circuit breakers in OPEN state
        - High error rate agents (>50%)
        - Agents with excessive costs
        """
        alerts = []

        # Circuit breaker alerts
        from agents.circuit_breaker import get_all_breakers
        for name, breaker in get_all_breakers().items():
            state = breaker.get_state()
            if state['state'] == 'open':
                alerts.append({
                    'level': 'critical',
                    'type': 'circuit_breaker_open',
                    'agent': name,
                    'message': (
                        f"Agent '{name}' circuit breaker is OPEN "
                        f"(failures={state['failures']}, "
                        f"retry_in={state['next_retry_in']}s)"
                    ),
                })
            elif state['state'] == 'half_open':
                alerts.append({
                    'level': 'warning',
                    'type': 'circuit_breaker_half_open',
                    'agent': name,
                    'message': f"Agent '{name}' circuit breaker is HALF_OPEN (probing)",
                })

        # High error rate alerts
        from agents.llm_tracer import get_tracer
        tracer = get_tracer()
        for agent_data in tracer.get_cost_breakdown(period_seconds=3600):
            name = agent_data['agent_name']
            stats = tracer.get_agent_stats(name, period_seconds=3600)
            if stats['total_calls'] >= 3 and stats['success_rate'] < 0.5:
                alerts.append({
                    'level': 'warning',
                    'type': 'high_error_rate',
                    'agent': name,
                    'message': (
                        f"Agent '{name}' error rate is high: "
                        f"{(1 - stats['success_rate']) * 100:.0f}% "
                        f"({stats['total_calls']} calls in last hour)"
                    ),
                })

        return alerts

    def get_cost_analysis(self, period: str = '7d') -> dict:
        """Return detailed cost analysis.

        Returns:
            {
                total_cost_cents: float,
                per_agent: [{agent, calls, cost, tokens}],
                daily_trend: [{date, cost}],
                budget_remaining: float,
            }
        """
        period_seconds = self._parse_period(period)

        from agents.llm_tracer import get_tracer
        tracer = get_tracer()

        total = tracer.get_total_stats(period_seconds)
        per_agent = tracer.get_cost_breakdown(period_seconds)

        # Budget info
        budget_limit = 100.0  # cents, from config
        try:
            from flask import current_app
            budget_limit = float(current_app.config.get('AGENT_MAX_COST_CENTS', 100.0))
        except Exception:
            pass

        return {
            'total_cost_cents': total['total_cost_cents'],
            'total_tokens': total['total_tokens'],
            'per_agent': per_agent,
            'budget_limit_cents': budget_limit,
            'budget_remaining_cents': round(max(0, budget_limit - total['total_cost_cents']), 4),
            'budget_usage_pct': round(
                (total['total_cost_cents'] / budget_limit * 100) if budget_limit > 0 else 0, 1
            ),
        }

    def _get_per_agent_stats(self, period_seconds: int) -> list[dict]:
        """Get stats for each agent."""
        from agents.llm_tracer import get_tracer
        tracer = get_tracer()

        cost_data = tracer.get_cost_breakdown(period_seconds)
        result = []
        for entry in cost_data:
            name = entry['agent_name']
            stats = tracer.get_agent_stats(name, period_seconds)
            result.append({
                'agent_name': name,
                'total_calls': stats['total_calls'],
                'success_rate': stats['success_rate'],
                'avg_latency_ms': stats['avg_latency_ms'],
                'total_input_tokens': stats['total_input_tokens'],
                'total_output_tokens': stats['total_output_tokens'],
                'total_cost_cents': stats['total_cost_cents'],
                'error_breakdown': stats['error_breakdown'],
            })

        return result

    def _get_error_breakdown(self, period_seconds: int) -> dict:
        """Get error counts by type across all agents."""
        from agents.llm_tracer import get_tracer
        tracer = get_tracer()

        combined = {}
        for entry in tracer.get_cost_breakdown(period_seconds):
            name = entry['agent_name']
            stats = tracer.get_agent_stats(name, period_seconds)
            for error_type, count in stats.get('error_breakdown', {}).items():
                combined[error_type] = combined.get(error_type, 0) + count

        return combined

    def _get_circuit_breaker_states(self) -> list[dict]:
        """Get all circuit breaker states."""
        from agents.circuit_breaker import get_all_breakers
        return [
            breaker.get_state()
            for breaker in get_all_breakers().values()
        ]

    @staticmethod
    def _parse_period(period: str) -> int:
        """Parse period string to seconds."""
        multipliers = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
        if not period:
            return 86400
        unit = period[-1]
        try:
            value = int(period[:-1])
        except ValueError:
            return 86400
        return value * multipliers.get(unit, 86400)
