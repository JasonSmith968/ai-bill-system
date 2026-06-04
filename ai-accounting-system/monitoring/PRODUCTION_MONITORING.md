# Production Monitoring Guide

## Overview

The monitoring system tracks 4 key dimensions of the AI Accounting System:

| Dimension | Metrics Source | Dashboard |
|-----------|---------------|-----------|
| AI Cost | AgentExecutionLog, AIUsage | Grafana + Daily Report |
| System Stability | Prometheus (node, redis, mysql, celery) | Grafana |
| Stripe | ProcessedEvent, Payment, Subscription | Daily Report |
| User Behavior | LoginHistory, Transaction, AgentExecutionLog | Daily Report |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Monitoring Stack                      │
├─────────────┬─────────────┬─────────────┬───────────────┤
│ Prometheus  │   Grafana   │ Alertmanager│   Filebeat    │
│  (metrics)  │(dashboards) │  (alerts)   │   (logs)      │
├─────────────┴─────────────┴─────────────┴───────────────┤
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │  Node    │ │  Redis   │ │  MySQL   │ │  Flask   │   │
│  │ Exporter │ │ Exporter │ │ Exporter │ │  /metrics│   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Daily Report Generator (production_metrics.py)  │   │
│  │  - AI cost aggregation                           │   │
│  │  - System health snapshot                        │   │
│  │  - Stripe payment stats                          │   │
│  │  - User behavior analytics                       │   │
│  │  - Anomaly detection                             │   │
│  │  - Scaling recommendations                       │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Daily Production Report

### Automated Generation

```bash
# Run manually
python monitoring/scripts/production_metrics.py --output report --period 1d

# Run via cron (8 AM daily)
0 8 * * * /opt/ai-accounting-system/monitoring/scripts/daily_report.sh

# JSON output for dashboards
python monitoring/scripts/production_metrics.py --output json --period 7d --save report.json
```

### Report Sections

**1. AI Cost**
- Total cost (USD) for the period
- Token consumption by model (input/output)
- Per-user cost ranking (top 20)
- Per-agent breakdown (calls, cost, latency, success rate)
- Daily cost trend

**2. System Health**
- Host: memory, CPU load, disk
- Docker: per-container CPU/memory/network
- Redis: memory usage, fragmentation, connected clients
- Celery: queue lengths per queue (ai, ocr, email, report)
- MySQL: connection count

**3. Stripe**
- Payment success rate
- Revenue (daily trend)
- New subscriptions vs churned
- Webhook event count
- Failed payments (recent 10)

**4. User Behavior**
- DAU / WAU / MAU
- DAU/MAU ratio (stickiness)
- Retention rate (period over period)
- New registrations
- Feature usage (transactions, AI calls, logins)

**5. Anomaly Detection**
- AI cost per user > $5/period
- Agent success rate < 80%
- Memory > 85%
- Disk > 85%
- CPU load > 4
- Redis fragmentation > 1.5
- Celery queue backlog > 100
- Payment success rate < 90%
- Retention rate < 50%

**6. Scaling Recommendations**
- Server: memory/CPU/disk analysis
- Celery: queue backlog analysis
- AI cost: optimization suggestions
- Per-container: memory leak detection

## Grafana Dashboards

### Access

```bash
# SSH tunnel (monitoring ports are not publicly exposed)
ssh -L 3000:localhost:3000 root@YOUR_SERVER

# Open http://localhost:3000
# Login: admin / (see GRAFANA_PASSWORD in .env.production)
```

### Available Dashboards

| Dashboard | UID | Description |
|-----------|-----|-------------|
| App Overview | ai-app-overview | Request rate, error rate, latency, active requests |
| Production Monitoring | ai-prod-monitoring | Full production view (AI, infra, Celery, DB) |

### Production Monitoring Panels

**Row 1: System Overview**
- Request rate (req/s)
- Error rate (5xx %)
- Latency P50/P95/P99
- Active requests gauge

**Row 2: Infrastructure**
- CPU usage
- Memory usage
- Redis memory
- MySQL connections

**Row 3: Celery Queues**
- Queue length per queue
- Task success rate

**Row 4: AI / LLM**
- AI call rate per agent
- AI error rate per agent
- AI latency P95 per agent
- Circuit breaker status

**Row 5: Token Usage**
- Token usage by model
- Estimated cost by model

**Row 6: Database**
- ORM operations rate
- ORM errors
- Session duration P95

## Alert Rules

### System Alerts

| Alert | Condition | Severity | Duration |
|-------|-----------|----------|----------|
| ServiceDown | up == 0 | critical | 1m |
| HighErrorRate | 5xx > 5% | warning | 5m |
| HighLatency | P95 > 5s | warning | 5m |
| RedisHighMemory | > 80% maxmemory | warning | 5m |
| MySQLHighConnections | > 80% max | warning | 5m |
| DiskSpaceLow | < 15% free | warning | 5m |
| HighCPUUsage | > 85% | warning | 10m |

### AI Alerts

| Alert | Condition | Severity | Duration |
|-------|-----------|----------|----------|
| AIHighErrorRate | > 20% per agent | warning | 5m |
| AIHighLatency | P95 > 30s | warning | 5m |
| CircuitBreakerOpen | state == OPEN | critical | 2m |

### Celery Alerts

| Alert | Condition | Severity | Duration |
|-------|-----------|----------|----------|
| CeleryQueueBacklog | > 500 tasks | warning | 10m |

### Stripe Alerts

| Alert | Condition | Severity | Duration |
|-------|-----------|----------|----------|
| StripeWebhookStale | no events in 1h | warning | 15m |
| StripeHighFailureRate | > 10% failures | warning | 5m |

## Prometheus Configuration

Scrape targets (configured in `monitoring/prometheus.yml`):

| Job | Target | Interval | Purpose |
|-----|--------|----------|---------|
| prometheus | localhost:9090 | 15s | Self-monitoring |
| backend | backend:5000/metrics | 10s | Flask app metrics |
| node-exporter | node-exporter:9100 | 15s | Host metrics |
| redis-exporter | redis-exporter:9121 | 15s | Redis metrics |
| mysql-exporter | mysql-exporter:9104 | 15s | MySQL metrics |

## Log Monitoring

### ELK Stack

- **Elasticsearch**: Log storage and search (port 9200, localhost only)
- **Kibana**: Log visualization (port 5601, localhost only)
- **Filebeat**: Log collection from nginx and backend containers

### Access

```bash
# SSH tunnel
ssh -L 5601:localhost:5601 root@YOUR_SERVER
# Open http://localhost:5601
```

### Log Patterns to Watch

```bash
# Errors
docker logs ai-backend 2>&1 | grep -iE 'error|exception|fatal'

# Slow requests
docker logs ai-backend 2>&1 | grep -E 'duration=[0-9]{4,}ms'

# Security events
docker logs ai-nginx 2>&1 | grep -E '" 40[13] |" 429 '
```

## Maintenance

### Adding Custom Metrics

1. Add Prometheus metric in `backend/app.py` or relevant module
2. Update `monitoring/grafana/dashboards/production-monitoring.json`
3. Add alert rule in `monitoring/rules/alerts.yml` if needed

### Rotating Reports

Reports auto-cleanup after 90 days (configured in `daily_report.sh`).

### Scaling Monitoring

For high-traffic deployments:
- Move Prometheus to dedicated instance
- Add Thanos for long-term storage
- Use Grafana Cloud for managed dashboards
- Add Loki for log aggregation (replace ELK)
