"""LLM call tracing — records metadata for every LLM call (no content for privacy).

Traces are stored in-memory with periodic flush to the AgentExecutionLog table.
This provides observability without storing sensitive prompt/completion content.
"""

import time
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_tracer = None


def get_tracer() -> 'LLMTracer':
    """Get or create the singleton LLMTracer."""
    global _tracer
    if _tracer is None:
        _tracer = LLMTracer()
    return _tracer


@dataclass
class TraceEntry:
    """A single LLM call trace (no content)."""
    agent_name: str
    request_id: Optional[str]
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    cost_cents: float
    success: bool
    error_type: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            'agent_name': self.agent_name,
            'request_id': self.request_id,
            'model': self.model,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.input_tokens + self.output_tokens,
            'duration_ms': self.duration_ms,
            'cost_cents': round(self.cost_cents, 4),
            'success': self.success,
            'error_type': self.error_type,
            'timestamp': self.timestamp,
        }


class LLMTracer:
    """Records metadata for every LLM call.

    Stores traces in a bounded in-memory deque. Periodically flushes
    aggregated stats to the AgentExecutionLog table.
    """

    def __init__(self, max_entries: int = 1000):
        self._traces: deque[TraceEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def trace_call(self, agent_name: str, request_id: Optional[str],
                   model: str, input_tokens: int, output_tokens: int,
                   duration_ms: int, cost_cents: float,
                   success: bool, error_type: Optional[str] = None):
        """Record an LLM call trace.

        Args:
            agent_name: Name of the calling agent
            request_id: Request correlation ID
            model: Model used (e.g. 'deepseek-chat')
            input_tokens: Prompt token count
            output_tokens: Completion token count
            duration_ms: Call duration in milliseconds
            cost_cents: Estimated cost in cents
            success: Whether the call succeeded
            error_type: Error classification (if failed)
        """
        entry = TraceEntry(
            agent_name=agent_name,
            request_id=request_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            cost_cents=cost_cents,
            success=success,
            error_type=error_type,
        )

        with self._lock:
            self._traces.append(entry)

        # Persist to DB asynchronously (best-effort)
        self._persist_trace(entry)

    def get_recent_traces(self, limit: int = 50) -> list[dict]:
        """Return recent traces (most recent first)."""
        with self._lock:
            entries = list(self._traces)
        entries.reverse()
        return [e.to_dict() for e in entries[:limit]]

    def get_agent_stats(self, agent_name: str, period_seconds: int = 86400) -> dict:
        """Return aggregated stats for an agent within a time window."""
        cutoff = time.time() - period_seconds
        with self._lock:
            entries = [
                e for e in self._traces
                if e.agent_name == agent_name and e.timestamp >= cutoff
            ]

        if not entries:
            return {
                'agent_name': agent_name,
                'total_calls': 0,
                'success_rate': 0.0,
                'avg_latency_ms': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_cost_cents': 0.0,
                'error_breakdown': {},
            }

        successes = sum(1 for e in entries if e.success)
        total_latency = sum(e.duration_ms for e in entries)
        total_input = sum(e.input_tokens for e in entries)
        total_output = sum(e.output_tokens for e in entries)
        total_cost = sum(e.cost_cents for e in entries)

        error_breakdown = {}
        for e in entries:
            if not e.success and e.error_type:
                error_breakdown[e.error_type] = error_breakdown.get(e.error_type, 0) + 1

        return {
            'agent_name': agent_name,
            'total_calls': len(entries),
            'success_rate': round(successes / len(entries), 4),
            'avg_latency_ms': int(total_latency / len(entries)),
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'total_cost_cents': round(total_cost, 4),
            'error_breakdown': error_breakdown,
        }

    def get_cost_breakdown(self, period_seconds: int = 86400) -> list[dict]:
        """Return per-agent cost breakdown within a time window."""
        cutoff = time.time() - period_seconds
        with self._lock:
            entries = [e for e in self._traces if e.timestamp >= cutoff]

        by_agent: dict[str, dict] = {}
        for e in entries:
            if e.agent_name not in by_agent:
                by_agent[e.agent_name] = {
                    'agent_name': e.agent_name,
                    'calls': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'cost_cents': 0.0,
                }
            agg = by_agent[e.agent_name]
            agg['calls'] += 1
            agg['input_tokens'] += e.input_tokens
            agg['output_tokens'] += e.output_tokens
            agg['cost_cents'] += e.cost_cents

        result = sorted(by_agent.values(), key=lambda x: x['cost_cents'], reverse=True)
        for r in result:
            r['cost_cents'] = round(r['cost_cents'], 4)
        return result

    def get_total_stats(self, period_seconds: int = 86400) -> dict:
        """Return total stats across all agents."""
        cutoff = time.time() - period_seconds
        with self._lock:
            entries = [e for e in self._traces if e.timestamp >= cutoff]

        if not entries:
            return {
                'total_calls': 0, 'success_rate': 0.0,
                'avg_latency_ms': 0, 'total_cost_cents': 0.0,
                'total_tokens': 0,
            }

        successes = sum(1 for e in entries if e.success)
        return {
            'total_calls': len(entries),
            'success_rate': round(successes / len(entries), 4),
            'avg_latency_ms': int(sum(e.duration_ms for e in entries) / len(entries)),
            'total_cost_cents': round(sum(e.cost_cents for e in entries), 4),
            'total_tokens': sum(e.input_tokens + e.output_tokens for e in entries),
        }

    def clear(self):
        """Clear all traces (for testing)."""
        with self._lock:
            self._traces.clear()

    def _persist_trace(self, entry: TraceEntry):
        """Best-effort persist to AgentExecutionLog.

        Only writes token/cost fields; does NOT store prompt or completion content.
        """
        try:
            from flask import has_app_context
            if not has_app_context():
                return

            from models.agent_log import AgentExecutionLog
            from extensions import db

            log = AgentExecutionLog(
                agent_name=entry.agent_name,
                request_id=entry.request_id or '',
                success=entry.success,
                duration_ms=entry.duration_ms,
                error_message=entry.error_type if not entry.success else None,
                input_tokens=entry.input_tokens,
                output_tokens=entry.output_tokens,
                cost_cents=entry.cost_cents,
                model=entry.model,
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            # Tracer persistence must never break the main flow
            logger.debug(f"Trace persist failed (non-critical): {e}")
            try:
                from extensions import db
                db.session.rollback()
            except Exception:
                pass
