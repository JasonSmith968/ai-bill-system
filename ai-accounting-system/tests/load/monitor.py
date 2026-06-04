"""System resource monitor for load testing.

Collects CPU, memory, and process metrics during test runs.
Run alongside k6 tests to capture system behavior under load.

Usage:
    python tests/load/monitor.py [--duration 600] [--interval 5] [--output results/system_metrics.json]
"""

import argparse
import json
import time
import os
import sys
from datetime import datetime

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_system_metrics():
    """Collect current system metrics."""
    metrics = {
        'timestamp': datetime.utcnow().isoformat(),
    }

    if HAS_PSUTIL:
        metrics['cpu_percent'] = psutil.cpu_percent(interval=1)
        metrics['cpu_count'] = psutil.cpu_count()
        mem = psutil.virtual_memory()
        metrics['memory_total_mb'] = mem.total / (1024 * 1024)
        metrics['memory_used_mb'] = mem.used / (1024 * 1024)
        metrics['memory_percent'] = mem.percent
        disk = psutil.disk_usage('/')
        metrics['disk_used_gb'] = disk.used / (1024 * 1024 * 1024)
        metrics['disk_percent'] = disk.percent

        # Network I/O
        net = psutil.net_io_counters()
        metrics['net_bytes_sent'] = net.bytes_sent
        metrics['net_bytes_recv'] = net.bytes_recv

        # Find Python processes (Flask server)
        python_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                if 'python' in proc.info['name'].lower():
                    python_procs.append({
                        'pid': proc.info['pid'],
                        'cpu_percent': proc.info['cpu_percent'],
                        'memory_mb': proc.info['memory_info'].rss / (1024 * 1024) if proc.info['memory_info'] else 0,
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        metrics['python_processes'] = python_procs
    else:
        # Fallback: read /proc on Linux or use basic Windows metrics
        try:
            import subprocess
            if sys.platform == 'win32':
                result = subprocess.run(
                    ['wmic', 'cpu', 'get', 'loadpercentage', '/value'],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split('\n'):
                    if 'LoadPercentage' in line:
                        metrics['cpu_percent'] = float(line.split('=')[1].strip())
            else:
                with open('/proc/loadavg') as f:
                    load = f.read().split()
                    metrics['load_1m'] = float(load[0])
                    metrics['load_5m'] = float(load[1])
                    metrics['load_15m'] = float(load[2])
        except Exception:
            pass

    return metrics


def monitor_loop(duration, interval, output_path):
    """Collect metrics at regular intervals."""
    print(f"Monitoring system for {duration}s (interval={interval}s)")
    print(f"Output: {output_path}")
    print()

    metrics_list = []
    start = time.time()

    while time.time() - start < duration:
        try:
            m = get_system_metrics()
            metrics_list.append(m)

            elapsed = time.time() - start
            cpu = m.get('cpu_percent', 'N/A')
            mem = m.get('memory_percent', 'N/A')
            print(f"  [{elapsed:6.0f}s] CPU: {cpu}%  Memory: {mem}%")

        except Exception as e:
            print(f"  Error collecting metrics: {e}")

        time.sleep(interval)

    # Summary
    if metrics_list:
        cpu_values = [m['cpu_percent'] for m in metrics_list if 'cpu_percent' in m]
        mem_values = [m['memory_percent'] for m in metrics_list if 'memory_percent' in m]

        summary = {
            'duration_seconds': duration,
            'interval_seconds': interval,
            'samples': len(metrics_list),
        }

        if cpu_values:
            summary['cpu_avg'] = sum(cpu_values) / len(cpu_values)
            summary['cpu_max'] = max(cpu_values)
            summary['cpu_min'] = min(cpu_values)

        if mem_values:
            summary['memory_avg'] = sum(mem_values) / len(mem_values)
            summary['memory_max'] = max(mem_values)
            summary['memory_min'] = min(mem_values)

        result = {
            'summary': summary,
            'samples': metrics_list,
        }
    else:
        result = {'summary': {}, 'samples': []}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\nResults saved to {output_path}")
    return result


def main():
    parser = argparse.ArgumentParser(description='System resource monitor')
    parser.add_argument('--duration', type=int, default=600, help='Monitoring duration in seconds')
    parser.add_argument('--interval', type=int, default=5, help='Sampling interval in seconds')
    parser.add_argument('--output', default='tests/load/results/system_metrics.json', help='Output file')
    args = parser.parse_args()

    monitor_loop(args.duration, args.interval, args.output)


if __name__ == '__main__':
    main()
