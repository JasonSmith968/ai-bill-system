"""System Health — infrastructure monitoring for admin console.

Checks: database, Redis, disk, memory, Docker containers, application.
"""

import os
import time
import logging
import subprocess
from datetime import datetime

from extensions import db
from sqlalchemy import text

logger = logging.getLogger(__name__)


def check_database() -> dict:
    """Check MySQL connectivity and pool status."""
    start = time.time()
    try:
        result = db.session.execute(text("SELECT 1")).scalar()
        latency_ms = round((time.time() - start) * 1000, 1)

        # Pool stats
        pool = db.engine.pool
        pool_status = {
            'size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
        }

        # Table counts
        tables = db.session.execute(text(
            "SELECT table_name, table_rows FROM information_schema.tables "
            "WHERE table_schema = DATABASE() ORDER BY table_rows DESC LIMIT 10"
        )).fetchall()

        return {
            'status': 'healthy',
            'latency_ms': latency_ms,
            'pool': pool_status,
            'top_tables': [{'name': t[0], 'rows': t[1] or 0} for t in tables],
        }
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}


def check_redis() -> dict:
    """Check Redis connectivity and memory usage."""
    try:
        import redis
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url, socket_timeout=5)

        start = time.time()
        r.ping()
        latency_ms = round((time.time() - start) * 1000, 1)

        info = r.info('memory')
        clients = r.info('clients')
        stats = r.info('stats')

        return {
            'status': 'healthy',
            'latency_ms': latency_ms,
            'memory': {
                'used_mb': round(info.get('used_memory', 0) / 1024 / 1024, 1),
                'peak_mb': round(info.get('used_memory_peak', 0) / 1024 / 1024, 1),
                'fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
            },
            'clients': {
                'connected': clients.get('connected_clients', 0),
                'blocked': clients.get('blocked_clients', 0),
            },
            'stats': {
                'total_connections': stats.get('total_connections_received', 0),
                'total_commands': stats.get('total_commands_processed', 0),
                'keyspace_hits': stats.get('keyspace_hits', 0),
                'keyspace_misses': stats.get('keyspace_misses', 0),
            },
        }
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}


def check_disk() -> dict:
    """Check disk usage."""
    try:
        st = os.statvfs('/')
        total_gb = round(st.f_blocks * st.f_frsize / 1024**3, 1)
        free_gb = round(st.f_bavail * st.f_frsize / 1024**3, 1)
        used_gb = round(total_gb - free_gb, 1)
        used_pct = round(used_gb / total_gb * 100, 1) if total_gb > 0 else 0

        status = 'healthy'
        if used_pct > 90:
            status = 'critical'
        elif used_pct > 80:
            status = 'warning'

        return {
            'status': status,
            'total_gb': total_gb,
            'used_gb': used_gb,
            'free_gb': free_gb,
            'used_pct': used_pct,
        }
    except Exception as e:
        return {'status': 'unknown', 'error': str(e)}


def check_memory() -> dict:
    """Check system memory usage."""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()

        mem = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(':')
                value = int(parts[1])  # in kB
                mem[key] = value

        total_mb = round(mem.get('MemTotal', 0) / 1024, 0)
        available_mb = round(mem.get('MemAvailable', 0) / 1024, 0)
        used_mb = round(total_mb - available_mb, 0)
        used_pct = round(used_mb / total_mb * 100, 1) if total_mb > 0 else 0

        swap_total = round(mem.get('SwapTotal', 0) / 1024, 0)
        swap_free = round(mem.get('SwapFree', 0) / 1024, 0)

        status = 'healthy'
        if used_pct > 90:
            status = 'critical'
        elif used_pct > 80:
            status = 'warning'

        return {
            'status': status,
            'total_mb': total_mb,
            'used_mb': used_mb,
            'available_mb': available_mb,
            'used_pct': used_pct,
            'swap_total_mb': swap_total,
            'swap_used_mb': swap_total - swap_free,
        }
    except Exception as e:
        return {'status': 'unknown', 'error': str(e)}


def check_containers() -> list[dict]:
    """Check Docker container status."""
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--format',
             '{{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return [{'status': 'unknown', 'error': 'docker ps failed'}]

        containers = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                name = parts[0]
                status_str = parts[1]
                ports = parts[2] if len(parts) > 2 else ''
                image = parts[3] if len(parts) > 3 else ''

                status = 'running' if 'Up' in status_str else 'stopped'
                health = 'healthy'
                if 'unhealthy' in status_str.lower():
                    health = 'unhealthy'
                elif 'health' in status_str.lower() and 'healthy' not in status_str.lower():
                    health = 'starting'

                containers.append({
                    'name': name,
                    'status': status,
                    'health': health,
                    'image': image,
                    'ports': ports,
                    'status_text': status_str,
                })

        return containers
    except FileNotFoundError:
        return [{'status': 'unknown', 'error': 'docker not installed'}]
    except Exception as e:
        return [{'status': 'unknown', 'error': str(e)}]


def check_application() -> dict:
    """Check application-level health."""
    try:
        from models.user import User
        from models.transaction import Transaction
        from models.agent_log import AgentExecutionLog

        user_count = User.query.count()
        active_users_today = db.session.execute(text(
            "SELECT COUNT(DISTINCT user_id) FROM login_history "
            "WHERE login_at >= CURDATE() AND success = 1"
        )).scalar() or 0

        tx_today = db.session.execute(text(
            "SELECT COUNT(*) FROM transactions WHERE created_at >= CURDATE()"
        )).scalar() or 0

        ai_calls_today = db.session.execute(text(
            "SELECT COUNT(*) FROM agent_execution_logs WHERE created_at >= CURDATE()"
        )).scalar() or 0

        return {
            'status': 'healthy',
            'total_users': user_count,
            'active_users_today': active_users_today,
            'transactions_today': tx_today,
            'ai_calls_today': ai_calls_today,
        }
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}


def get_system_health() -> dict:
    """Full system health check."""
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'database': check_database(),
        'redis': check_redis(),
        'disk': check_disk(),
        'memory': check_memory(),
        'containers': check_containers(),
        'application': check_application(),
        'overall': _compute_overall_status(),
    }


def _compute_overall_status() -> str:
    """Compute overall system status from component checks."""
    db_status = check_database().get('status', 'unknown')
    redis_status = check_redis().get('status', 'unknown')

    if db_status == 'unhealthy' or redis_status == 'unhealthy':
        return 'critical'
    if db_status == 'warning' or redis_status == 'warning':
        return 'degraded'
    return 'healthy'
