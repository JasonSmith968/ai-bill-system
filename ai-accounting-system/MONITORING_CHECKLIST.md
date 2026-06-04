# Monitoring Checklist

## Monitoring Stack

| Component | Tool | Purpose |
|-----------|------|---------|
| Metrics | Prometheus + Grafana | System & app metrics |
| Logging | File-based + Sentry | Error tracking |
| Alerting | Prometheus Alertmanager | Threshold alerts |
| Uptime | External health check | Availability monitoring |
| Tracing | LLM Tracer (custom) | AI call chain tracing |

## Key Metrics to Monitor

### Application Metrics

| Metric | Threshold | Alert |
|--------|-----------|-------|
| `http_request_duration_seconds` p95 | < 1s | > 2s for 5m |
| `http_request_duration_seconds` p99 | < 3s | > 5s for 5m |
| `http_request_total` rate | baseline | > 2x baseline |
| `http_request_errors_total` rate | < 1% | > 5% for 5m |
| `flask_active_requests` | < 100 | > 200 for 5m |

### Database Metrics

| Metric | Threshold | Alert |
|--------|-----------|-------|
| `db_orm_operations_total` rate | baseline | spike > 3x |
| `db_orm_errors_total` rate | < 0.1% | > 1% for 5m |
| `db_session_duration_seconds` p95 | < 1s | > 5s for 5m |
| Connection pool utilization | < 80% | > 90% for 5m |
| Slow queries (> 1s) | < 10/hour | > 50/hour |

### AI/LLM Metrics

| Metric | Threshold | Alert |
|--------|-----------|-------|
| `ai_calls_total` rate | baseline | spike > 3x |
| `ai_errors_total` rate | < 5% | > 20% for 5m |
| `ai_latency_seconds` p95 | < 10s | > 30s for 5m |
| Circuit breaker state | CLOSED | OPEN for > 5m |
| Token usage | < budget | > 80% of budget |

### Infrastructure Metrics

| Metric | Threshold | Alert |
|--------|-----------|-------|
| CPU utilization | < 70% | > 85% for 10m |
| Memory utilization | < 80% | > 90% for 5m |
| Disk utilization | < 75% | > 85% |
| Network I/O | baseline | spike > 5x |
| File descriptors | < 80% limit | > 90% |

### Redis Metrics

| Metric | Threshold | Alert |
|--------|-----------|-------|
| Memory usage | < 80% maxmemory | > 90% |
| Connected clients | < 1000 | > 2000 |
| Hit rate | > 80% | < 50% |
| Evicted keys | 0 | > 100/min |
| Blocked clients | 0 | > 10 |

### Celery Metrics

| Metric | Threshold | Alert |
|--------|-----------|-------|
| Queue length | < 100 | > 1000 for 10m |
| Task success rate | > 95% | < 80% for 10m |
| Worker count | expected | < expected |
| Task duration p95 | < 30s | > 60s |

## Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

scrape_configs:
  - job_name: 'ai-accounting'
    metrics_path: '/metrics'
    bearer_token: 'YOUR_METRICS_TOKEN'
    static_configs:
      - targets: ['localhost:5000']
```

## Alert Rules

```yaml
# alert_rules.yml
groups:
  - name: ai-accounting
    rules:
      - alert: HighErrorRate
        expr: rate(http_request_errors_total[5m]) / rate(http_request_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate above 5%"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "p95 latency above 2s"

      - alert: HighMemoryUsage
        expr: node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Memory usage above 80%"

      - alert: DatabaseErrors
        expr: rate(db_orm_errors_total[5m]) > 0.01
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "ORM error rate above 1%"

      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state{state="open"} == 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker open for {{ $labels.agent }}"

      - alert: CeleryQueueBacklog
        expr: celery_queue_length > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Celery queue backlog above 1000"
```

## Grafana Dashboard Panels

### Overview Dashboard
1. Request rate (req/s) — time series
2. Error rate (%) — time series with threshold line
3. Latency percentiles (p50, p95, p99) — time series
4. Active requests — gauge
5. CPU/Memory — time series
6. DB connection pool — gauge

### AI Dashboard
1. AI call rate — time series
2. AI error rate — time series
3. AI latency distribution — histogram
4. Circuit breaker states — status panel
5. Token usage — counter with budget line
6. Per-agent breakdown — bar chart

### Database Dashboard
1. Query rate — time series
2. ORM error rate — time series
3. Session duration — histogram
4. Connection pool usage — gauge
5. Slow query count — counter
6. Tenant query distribution — pie chart

## Log Monitoring

### Critical Log Patterns to Watch

```bash
# Error patterns (alert immediately)
grep -E "ERROR|CRITICAL|FATAL" /var/log/ai-accounting/error.log

# ORM errors
grep "ObjectDeletedError\|IntegrityError\|OperationalError" /var/log/ai-accounting/error.log

# Security events
grep "401\|403\|Rate limit\|locked" /var/log/ai-accounting/access.log

# Performance issues
grep "Slow request\|timeout\|connection refused" /var/log/ai-accounting/app.log
```

### Log Rotation

```
/var/log/ai-accounting/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 www-data www-data
    postrotate
        systemctl reload gunicorn
    endscript
}
```

## Health Check Endpoint

```
GET /health

Response:
{
  "status": "ok",
  "timestamp": "2026-05-28T12:00:00Z"
}

External monitoring should:
1. Check every 30 seconds
2. Alert if 3 consecutive failures
3. Alert if response time > 5s
```

## On-Call Checklist

### Start of Shift
- [ ] Acknowledge PagerDuty/OpsGenie
- [ ] Review open incidents
- [ ] Check dashboards for anomalies
- [ ] Verify alert routing works

### During Shift
- [ ] Respond to alerts within 5 minutes
- [ ] Escalate if unresolved in 15 minutes
- [ ] Document all incidents
- [ ] Communicate status to stakeholders

### End of Shift
- [ ] Hand off open incidents
- [ ] Summarize shift activity
- [ ] Update runbooks if needed
