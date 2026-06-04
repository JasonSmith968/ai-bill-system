"""Per-agent circuit breaker with three states: CLOSED → OPEN → HALF_OPEN.

- CLOSED: normal operation, requests pass through
- OPEN: after N consecutive failures, circuit opens — requests get immediate fallback
- HALF_OPEN: after recovery_timeout, allow one probe request to test recovery
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

CLOSED = 'closed'
OPEN = 'open'
HALF_OPEN = 'half_open'

_breakers: dict[str, 'CircuitBreaker'] = {}
_lock = threading.Lock()


def get_breaker(agent_name: str, **kwargs) -> 'CircuitBreaker':
    """Get or create a circuit breaker for an agent."""
    if agent_name not in _breakers:
        with _lock:
            if agent_name not in _breakers:
                _breakers[agent_name] = CircuitBreaker(agent_name, **kwargs)
    return _breakers[agent_name]


def get_all_breakers() -> dict[str, 'CircuitBreaker']:
    """Return all circuit breakers (for monitoring)."""
    return dict(_breakers)


@dataclass
class CircuitBreaker:
    """Circuit breaker for a single agent/endpoint."""

    agent_name: str
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 1

    _state: str = field(default=CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0, init=False)
    _half_open_calls: int = field(default=0, init=False)

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        if self._state == CLOSED:
            return True

        if self._state == OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = HALF_OPEN
                self._half_open_calls = 0
                logger.info(f"Circuit breaker [{self.agent_name}] OPEN → HALF_OPEN after {elapsed:.0f}s")
                return True
            return False

        if self._state == HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls

        return False

    def record_success(self):
        """Record a successful call — reset to CLOSED."""
        if self._state == HALF_OPEN:
            logger.info(f"Circuit breaker [{self.agent_name}] HALF_OPEN → CLOSED (probe succeeded)")
        self._failures = 0
        self._state = CLOSED
        self._half_open_calls = 0

    def record_failure(self):
        """Record a failed call — may transition to OPEN."""
        self._failures += 1
        self._last_failure_time = time.time()

        if self._state == HALF_OPEN:
            self._state = OPEN
            logger.warning(f"Circuit breaker [{self.agent_name}] HALF_OPEN → OPEN (probe failed)")
            return

        if self._failures >= self.failure_threshold:
            self._state = OPEN
            logger.warning(
                f"Circuit breaker [{self.agent_name}] CLOSED → OPEN "
                f"(failures={self._failures}/{self.failure_threshold})"
            )

    def get_state(self) -> dict:
        """Return current breaker state for monitoring."""
        next_retry = None
        if self._state == OPEN:
            elapsed = time.time() - self._last_failure_time
            remaining = max(0, self.recovery_timeout - elapsed)
            next_retry = round(remaining, 1)

        return {
            'agent': self.agent_name,
            'state': self._state,
            'failures': self._failures,
            'threshold': self.failure_threshold,
            'last_failure': self._last_failure_time,
            'next_retry_in': next_retry,
        }

    @property
    def state(self) -> str:
        return self._state
