"""Structured error handling with classification and recovery strategies.

Classifies exceptions into categories and provides retry/fallback decisions.
"""

import time
import logging
import requests
from typing import Optional, Callable

logger = logging.getLogger(__name__)


# Error recovery strategies
ERROR_STRATEGIES = {
    'timeout': {
        'retry': True,
        'max_retries': 2,
        'backoff': 'exponential',
        'base_wait': 2.0,
        'fallback': 'local',
    },
    'rate_limit': {
        'retry': True,
        'max_retries': 3,
        'backoff': 'exponential',
        'base_wait': 4.0,
        'fallback': 'local',
    },
    'server_error': {
        'retry': True,
        'max_retries': 2,
        'backoff': 'exponential',
        'base_wait': 2.0,
        'fallback': 'local',
    },
    'auth_error': {
        'retry': False,
        'max_retries': 0,
        'backoff': None,
        'base_wait': 0,
        'fallback': 'local',
    },
    'quota_exceeded': {
        'retry': False,
        'max_retries': 0,
        'backoff': None,
        'base_wait': 0,
        'fallback': 'local',
    },
    'parse_error': {
        'retry': False,
        'max_retries': 0,
        'backoff': None,
        'base_wait': 0,
        'fallback': 'local',
    },
    'connection_error': {
        'retry': True,
        'max_retries': 2,
        'backoff': 'exponential',
        'base_wait': 1.0,
        'fallback': 'local',
    },
    'unknown': {
        'retry': True,
        'max_retries': 1,
        'backoff': 'linear',
        'base_wait': 1.0,
        'fallback': 'local',
    },
}


def classify_error(exc: Exception) -> str:
    """Classify an exception into an error category.

    Returns a key into ERROR_STRATEGIES.
    """
    if isinstance(exc, requests.Timeout):
        return 'timeout'

    if isinstance(exc, requests.ConnectionError):
        return 'connection_error'

    if isinstance(exc, requests.HTTPError):
        status = getattr(exc.response, 'status_code', 0) if hasattr(exc, 'response') else 0
        if status == 429:
            return 'rate_limit'
        if status in (401, 403):
            return 'auth_error'
        if status >= 500:
            return 'server_error'

    # Check for LLMClientError with specific messages
    exc_str = str(exc).lower()
    if 'timeout' in exc_str:
        return 'timeout'
    if 'rate limit' in exc_str or '429' in exc_str:
        return 'rate_limit'
    if 'quota' in exc_str or 'exceeded' in exc_str:
        return 'quota_exceeded'
    if 'parse' in exc_str or 'json' in exc_str:
        return 'parse_error'
    if 'api key' in exc_str or 'auth' in exc_str or '401' in exc_str:
        return 'auth_error'
    if '500' in exc_str or '502' in exc_str or '503' in exc_str:
        return 'server_error'

    return 'unknown'


def should_retry(error_type: str, attempt: int) -> bool:
    """Determine if a failed request should be retried."""
    strategy = ERROR_STRATEGIES.get(error_type, ERROR_STRATEGIES['unknown'])
    if not strategy['retry']:
        return False
    return attempt < strategy['max_retries']


def get_wait_seconds(error_type: str, attempt: int) -> float:
    """Calculate backoff wait time for a given error type and attempt number."""
    strategy = ERROR_STRATEGIES.get(error_type, ERROR_STRATEGIES['unknown'])
    base = strategy.get('base_wait', 1.0)

    if strategy['backoff'] == 'exponential':
        return base * (2 ** attempt)
    elif strategy['backoff'] == 'linear':
        return base * (attempt + 1)
    return base


def get_fallback_type(error_type: str) -> Optional[str]:
    """Get the fallback strategy type for an error."""
    strategy = ERROR_STRATEGIES.get(error_type, ERROR_STRATEGIES['unknown'])
    return strategy.get('fallback')


class ErrorRecovery:
    """Stateful error recovery handler for a single request context."""

    def __init__(self):
        self._attempt = 0
        self._last_error: Optional[Exception] = None
        self._error_history: list[dict] = []

    @property
    def attempt(self) -> int:
        return self._attempt

    def handle_error(self, exc: Exception) -> dict:
        """Record an error and return recovery decision.

        Returns:
            {
                'error_type': str,
                'should_retry': bool,
                'wait_seconds': float,
                'fallback': str | None,
                'attempt': int,
            }
        """
        self._attempt += 1
        self._last_error = exc
        error_type = classify_error(exc)

        self._error_history.append({
            'attempt': self._attempt,
            'error_type': error_type,
            'error': str(exc)[:200],
            'timestamp': time.time(),
        })

        decision = {
            'error_type': error_type,
            'should_retry': should_retry(error_type, self._attempt - 1),
            'wait_seconds': get_wait_seconds(error_type, self._attempt - 1),
            'fallback': get_fallback_type(error_type),
            'attempt': self._attempt,
        }

        logger.info(
            f"Error recovery: type={error_type} attempt={self._attempt} "
            f"retry={decision['should_retry']} wait={decision['wait_seconds']:.1f}s"
        )
        return decision

    def get_history(self) -> list[dict]:
        """Return error history for this request."""
        return self._error_history

    def reset(self):
        """Reset for a new request."""
        self._attempt = 0
        self._last_error = None
        self._error_history = []
