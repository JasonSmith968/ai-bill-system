# Production Admin Console

## Overview

Unified admin dashboard aggregating 9 operational sections: user management, subscription management, AI usage overview, token cost dashboard, growth metrics, Stripe revenue, system health, queue monitoring, and agent monitoring.

## Sections

### 1. User Management

User list with search, pagination, role/status filtering, and quick statistics.

**Endpoints:**
- `GET /api/admin/console/users` — paginated user list
- `GET /api/admin/console/users/stats` — user statistics

**Query parameters (users):**
- `search` — filter by username or email
- `role` — filter by role name (owner, member, admin)
- `status` — filter by active/inactive
- `page`, `per_page` — pagination

### 2. Subscription Management

Plan distribution and MRR overview.

**Endpoint:** `GET /api/admin/console/subscriptions`

**Returns:**
- `plan_distribution` — user count per plan (free, starter, pro, enterprise)
- `revenue` — MRR, ARR from Stripe

### 3. AI Usage Overview

Cost control dashboard with daily usage, top users, and cache/compression/routing savings.

**Endpoint:** `GET /api/admin/console/ai-usage`

**Returns:** Full cost control dashboard (same as `GET /api/cost-control/admin/dashboard`)

### 4. Token Cost Dashboard

Financial dashboard with token costs, savings, and optimization recommendations.

**Endpoint:** `GET /api/admin/console/token-cost?period=30`

**Query parameters:**
- `period` — analysis window in days (default: 30)

**Endpoint:** `GET /api/admin/console/cost-recommendations`

**Returns:** Actionable cost optimization tips

### 5. Growth Metrics

Growth analytics: new users, retention, referral funnel, affiliate stats.

**Endpoint:** `GET /api/admin/console/growth?period=30`

### 6. Stripe Revenue

Stripe revenue metrics, MRR, ARR, churn rate.

**Endpoint:** `GET /api/admin/console/revenue?period=30`

### 7. System Health

Infrastructure monitoring: database, Redis, disk, memory, Docker containers, application metrics.

**Endpoint:** `GET /api/admin/console/health`

**Returns:**
- `database` — connectivity, latency, pool stats, top tables
- `redis` — memory, clients, stats
- `disk` — usage percentage and free space
- `memory` — RAM usage and swap
- `containers` — Docker container status
- `application` — active users today, transactions today, AI calls today
- `overall` — computed status (healthy/degraded/critical)

### 8. Queue Monitoring

Celery queue and worker monitoring.

**Endpoint:** `GET /api/admin/console/queues`

**Returns:**
- `queues` — queue lengths and status (idle/busy/backlog) for ai, ocr, email, report
- `workers` — worker status, active tasks, concurrency, pool type
- `tasks` — task execution stats (success rate, avg duration, recent failures)
- `beat_schedule` — Celery Beat scheduled tasks

### 9. Agent Monitoring

Agent performance dashboard with per-agent stats.

**Endpoint:** `GET /api/admin/console/agents?period=24h`

**Query parameters:**
- `period` — analysis window (24h, 7d, 30d)

**Returns:** Per-agent call counts, success rate, latency, token usage, cost

## Unified Overview

All 9 sections in a single call:

**Endpoint:** `GET /api/admin/console/overview`

**Returns:**
```json
{
  "timestamp": "2026-05-28T10:00:00",
  "sections": {
    "users": {"total": 150, "active": 120, "active_today": 35},
    "subscriptions": {"mrr": 2500, "arr": 30000},
    "ai_usage": {...},
    "token_cost": {...},
    "growth": {...},
    "revenue": {...},
    "system_health": {...},
    "queues": {...},
    "agents": {...}
  }
}
```

## Authentication

All endpoints require admin authentication (`@token_required` + `@admin_required`).

## Usage

```bash
# Full overview (single call, all 9 sections)
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.example.com/api/admin/console/overview

# Individual sections
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.example.com/api/admin/console/users?search=john&page=1

curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.example.com/api/admin/console/health

curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.example.com/api/admin/console/queues

curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.example.com/api/admin/console/agents?period=7d

curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.example.com/api/admin/console/token-cost?period=30
```

## Data Flow

```
┌──────────────────────────────────────────────────────────┐
│                  Admin Console Routes                    │
│                  /api/admin/console/*                     │
└────────┬────────┬────────┬────────┬────────┬────────┬────┘
         │        │        │        │        │        │
         ▼        ▼        ▼        ▼        ▼        ▼
   ┌─────────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
   │  User   │ │Cost  │ │Growth│ │System│ │Queue │ │Agent │
   │  Model  │ │Ctrl  │ │Svc   │ │Health│ │Mon   │ │Mon   │
   └─────────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
         │        │        │        │        │        │
         ▼        ▼        ▼        ▼        ▼        ▼
   ┌──────────────────────────────────────────────────────┐
   │                    MySQL / Redis                      │
   └──────────────────────────────────────────────────────┘
```
