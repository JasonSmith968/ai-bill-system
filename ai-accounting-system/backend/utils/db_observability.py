"""DB session observability: tracks ORM operations, errors, and pool health.

Attach to the SQLAlchemy engine via event listeners. Metrics are exposed
through Prometheus counters/histograms when prometheus-client is installed,
otherwise they are written to the 'db' logger.
"""

import logging
import time
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from extensions import db

logger = logging.getLogger('db')

# --- Prometheus metrics (lazy, optional) ---
_metrics = None


def _get_metrics():
    """Return (orm_ops, orm_errors, session_duration) or Nones."""
    global _metrics
    if _metrics is not None:
        return _metrics
    try:
        from prometheus_client import Counter, Histogram
        orm_ops = Counter(
            'db_orm_operations_total',
            'Total ORM operations (flush/commit/query)',
            ['operation'],
        )
        orm_errors = Counter(
            'db_orm_errors_total',
            'Total ORM errors by exception type',
            ['error_type'],
        )
        session_duration = Histogram(
            'db_session_duration_seconds',
            'Time a session is held open',
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0, 30.0],
        )
        _metrics = (orm_ops, orm_errors, session_duration)
    except ImportError:
        _metrics = (None, None, None)
    return _metrics


# --- Session tracking state (per-session info stored via session.info) ---
_SESSION_START_KEY = 'db_obs_start'


@event.listens_for(Session, 'after_begin')
def _after_begin(session, transaction, connection):
    session.info[_SESSION_START_KEY] = time.monotonic()


@event.listens_for(Session, 'after_commit')
def _after_commit(session):
    orm_ops, _, session_duration = _get_metrics()
    if orm_ops:
        orm_ops.labels(operation='commit').inc()
    _record_session_duration(session)


@event.listens_for(Session, 'after_rollback')
def _after_rollback(session):
    orm_ops, orm_errors, session_duration = _get_metrics()
    if orm_ops:
        orm_ops.labels(operation='rollback').inc()
    if orm_errors:
        orm_errors.labels(error_type='rollback').inc()
    logger.warning("Session rolled back")
    _record_session_duration(session)


@event.listens_for(Session, 'after_soft_rollback')
def _after_soft_rollback(session, previous_transaction):
    """Fires on savepoint rollback too."""
    pass  # informational only


def _record_session_duration(session):
    """Record how long the session was held open."""
    _, _, session_duration = _get_metrics()
    start = session.info.pop(_SESSION_START_KEY, None)
    if session_duration and start:
        elapsed = time.monotonic() - start
        session_duration.observe(elapsed)


# --- ORM error wrapper (used by routes that catch ORM exceptions) ---
def record_orm_error(error_type: str):
    """Increment the ORM error counter for the given error type."""
    _, orm_errors, _ = _get_metrics()
    if orm_errors:
        orm_errors.labels(error_type=error_type).inc()
    logger.warning(f"ORM error recorded: {error_type}")


def init_db_observability(app):
    """Wire up DB observability hooks. Call from create_app()."""

    @app.before_request
    def _db_obs_request_start():
        from flask import g as flask_g
        flask_g._db_obs_request_start = time.monotonic()

    @app.after_request
    def _db_obs_request_end(response):
        from flask import g as flask_g, request
        start = getattr(flask_g, '_db_obs_request_start', None)
        if start:
            elapsed = time.monotonic() - start
            if elapsed > 2.0:
                logger.warning(
                    f"Slow request DB time: {request.method} {request.path} "
                    f"took {elapsed:.2f}s"
                )
        return response

    app.logger.info("DB session observability initialized")
