"""Cache decorators for AI results, user data, and dashboard queries."""

import hashlib
import functools
import logging
from flask import g

logger = logging.getLogger(__name__)


def _get_cache():
    """Lazy import to avoid circular dependency."""
    from cache import cache
    return cache


def _current_user_id():
    """Get current user ID from request context."""
    from flask import request
    if hasattr(request, 'current_user') and request.current_user:
        return request.current_user.id
    return None


def cached_ai_result(timeout=3600):
    """Cache AI/LLM analysis results by user_id + content hash.

    Usage:
        @cached_ai_result(timeout=3600)
        def analyze_spending(user_id, transactions_text):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            c = _get_cache()
            if c is None:
                return func(*args, **kwargs)

            # Build cache key from function name + user_id + content hash
            user_id = kwargs.get('user_id') or (args[0] if args else _current_user_id())
            content = str(args[1:]) + str(sorted(kwargs.items()))
            content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
            cache_key = f'ai:{func.__name__}:u{user_id}:{content_hash}'

            result = c.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return result

            result = func(*args, **kwargs)
            if result is not None:
                c.set(cache_key, result, timeout=timeout)
            return result
        return wrapper
    return decorator


def cached_user_data(timeout=300):
    """Cache user financial data queries (5 min default).

    Usage:
        @cached_user_data(timeout=300)
        def get_user_transactions(user_id, start_date, end_date):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            c = _get_cache()
            if c is None:
                return func(*args, **kwargs)

            user_id = kwargs.get('user_id') or (args[0] if args else _current_user_id())
            params_hash = hashlib.md5(str(args[1:]) .encode() + str(sorted(kwargs.items())).encode()).hexdigest()[:12]
            cache_key = f'data:{func.__name__}:u{user_id}:{params_hash}'

            result = c.get(cache_key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            if result is not None:
                c.set(cache_key, result, timeout=timeout)
            return result
        return wrapper
    return decorator


def cached_dashboard(timeout=120):
    """Cache dashboard data (2 min default).

    Usage:
        @cached_dashboard(timeout=120)
        def get_dashboard_stats(user_id):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            c = _get_cache()
            if c is None:
                return func(*args, **kwargs)

            user_id = kwargs.get('user_id') or (args[0] if args else _current_user_id())
            cache_key = f'dashboard:{func.__name__}:u{user_id}'

            result = c.get(cache_key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            if result is not None:
                c.set(cache_key, result, timeout=timeout)
            return result
        return wrapper
    return decorator


def invalidate_user_cache(user_id):
    """Clear all cached data for a specific user.

    Call this after user creates/modifies/deletes transactions.
    Note: Flask-Caching with Redis doesn't support prefix-delete natively,
    so we use a version counter approach.
    """
    c = _get_cache()
    if c is None:
        return

    # Increment user's cache version — all versioned keys become stale
    version_key = f'cache_version:u{user_id}'
    try:
        c.inc(version_key)
    except Exception:
        c.set(version_key, 1, timeout=86400)
    logger.debug(f"Invalidated cache for user {user_id}")
