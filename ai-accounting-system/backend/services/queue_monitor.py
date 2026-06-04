"""Queue Monitor — Celery queue and worker monitoring for admin console."""

import os
import logging
from datetime import datetime, timedelta

from extensions import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Queue names from celery_app.py
QUEUES = ['ai', 'ocr', 'email', 'report']


def get_queue_stats() -> list[dict]:
    """Get queue lengths from Redis."""
    try:
        import redis
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url, socket_timeout=5)

        queues = []
        for queue_name in QUEUES:
            length = r.llen(queue_name)
            queues.append({
                'name': queue_name,
                'length': length,
                'status': 'backlog' if length > 100 else 'busy' if length > 10 else 'idle',
            })

        return queues
    except Exception as e:
        logger.warning(f"Queue stats unavailable: {e}")
        return [{'name': q, 'length': 0, 'status': 'unknown'} for q in QUEUES]


def get_worker_stats() -> list[dict]:
    """Get Celery worker stats via Celery inspect."""
    try:
        from celery_app import celery
        inspector = celery.control.inspect(timeout=5.0)

        workers = []
        active = inspector.active() or {}
        registered = inspector.registered() or {}
        stats = inspector.stats() or {}

        for worker_name, worker_stats in stats.items():
            active_tasks = active.get(worker_name, [])
            registered_tasks = registered.get(worker_name, [])

            workers.append({
                'name': worker_name,
                'status': 'online',
                'active_tasks': len(active_tasks),
                'registered_tasks': len(registered_tasks),
                'total_processed': worker_stats.get('total', {}).get('tasks.ai_tasks.run_llm_analysis', 0),
                'pool': worker_stats.get('pool', {}).get('implementation', 'unknown'),
                'concurrency': worker_stats.get('pool', {}).get('max-concurrency', 0),
            })

        return workers
    except Exception as e:
        logger.warning(f"Worker stats unavailable: {e}")
        return []


def get_task_stats(hours: int = 24) -> dict:
    """Get task execution statistics from DB."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    try:
        # Task counts by type and status
        rows = db.session.execute(text("""
            SELECT task_type, status, COUNT(*) AS cnt
            FROM task_records
            WHERE created_at >= :cutoff
            GROUP BY task_type, status
        """), {'cutoff': cutoff}).fetchall()

        by_type = {}
        for task_type, status, cnt in rows:
            if task_type not in by_type:
                by_type[task_type] = {'total': 0, 'success': 0, 'failed': 0, 'pending': 0, 'running': 0}
            by_type[task_type][status] = by_type[task_type].get(status, 0) + cnt
            by_type[task_type]['total'] += cnt

        # Total stats
        total = sum(v['total'] for v in by_type.values())
        total_success = sum(v.get('success', 0) for v in by_type.values())
        total_failed = sum(v.get('failed', 0) for v in by_type.values())

        # Recent task durations
        durations = db.session.execute(text("""
            SELECT task_type,
                   AVG(TIMESTAMPDIFF(SECOND, started_at, completed_at)) AS avg_duration_s
            FROM task_records
            WHERE created_at >= :cutoff
              AND started_at IS NOT NULL
              AND completed_at IS NOT NULL
              AND status = 'success'
            GROUP BY task_type
        """), {'cutoff': cutoff}).fetchall()

        avg_durations = {row[0]: round(float(row[1] or 0), 1) for row in durations}

        # Failed tasks (recent)
        failed_tasks = db.session.execute(text("""
            SELECT task_id, task_type, error, created_at
            FROM task_records
            WHERE created_at >= :cutoff AND status = 'failed'
            ORDER BY created_at DESC
            LIMIT 10
        """), {'cutoff': cutoff}).fetchall()

        return {
            'period_hours': hours,
            'total': total,
            'success': total_success,
            'failed': total_failed,
            'success_rate_pct': round(total_success / total * 100, 1) if total > 0 else 0,
            'by_type': by_type,
            'avg_duration_seconds': avg_durations,
            'recent_failures': [
                {
                    'task_id': row[0],
                    'task_type': row[1],
                    'error': (row[2] or '')[:200],
                    'created_at': row[3].isoformat() if row[3] else None,
                }
                for row in failed_tasks
            ],
        }
    except Exception as e:
        logger.warning(f"Task stats unavailable: {e}")
        return {'period_hours': hours, 'total': 0, 'error': str(e)}


def get_beat_schedule() -> list[dict]:
    """Get Celery Beat scheduled tasks."""
    try:
        from celery_app import celery
        schedule = celery.conf.beat_schedule or {}

        tasks = []
        for name, entry in schedule.items():
            tasks.append({
                'name': name,
                'task': entry.get('task', ''),
                'schedule': str(entry.get('schedule', '')),
            })

        return tasks
    except Exception as e:
        logger.warning(f"Beat schedule unavailable: {e}")
        return []


def get_queue_monitor() -> dict:
    """Full queue monitoring dashboard."""
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'queues': get_queue_stats(),
        'workers': get_worker_stats(),
        'tasks': get_task_stats(hours=24),
        'beat_schedule': get_beat_schedule(),
    }
