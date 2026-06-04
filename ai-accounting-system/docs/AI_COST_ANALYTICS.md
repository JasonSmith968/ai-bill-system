# AI Cost Analytics System

## Overview

Real-time cost analysis system for tracking AI SaaS profitability. Calculates gross margin, per-user economics, and generates cost alerts.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Financial Analytics Pipeline                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ AgentExecLog │  │  Subscription │  │      Payment         │  │
│  │  (AI costs)  │  │   (MRR/ARR)  │  │    (Revenue)         │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│         ▼                 ▼                      ▼              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              cost_analytics.py (Service)                │   │
│  │                                                         │   │
│  │  • get_per_user_cost()       • get_revenue_metrics()   │   │
│  │  • get_per_feature_cost()    • get_gross_margin()       │   │
│  │  • get_model_comparison()    • get_cache_savings()      │   │
│  │  • get_free_user_burn_rate() • check_cost_alerts()      │   │
│  │  • get_financial_dashboard()                            │   │
│  └──────────────┬──────────────────────────┬──────────────┘   │
│                 │                          │                   │
│         ┌───────▼───────┐          ┌──────▼──────────┐       │
│         │  API Routes   │          │  Prometheus     │       │
│         │ /api/analytics│          │  Exporter       │       │
│         └───────────────┘          └─────────────────┘       │
│                                                                │
│         ┌───────────────┐          ┌─────────────────┐       │
│         │   Grafana     │          │  Alert Rules    │       │
│         │  Dashboard    │          │  (6 alerts)     │       │
│         └───────────────┘          └─────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## API Endpoints

All endpoints require admin authentication (`@token_required` + `@admin_required`).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/analytics/dashboard` | GET | Complete financial dashboard |
| `GET /api/analytics/gross-margin` | GET | Gross margin analysis |
| `GET /api/analytics/revenue` | GET | MRR, ARR, ARPU, LTV |
| `GET /api/analytics/cost/per-user` | GET | Per-user token cost |
| `GET /api/analytics/cost/per-feature` | GET | Per-feature cost |
| `GET /api/analytics/cost/models` | GET | Model cost comparison |
| `GET /api/analytics/cost/cache-savings` | GET | Cache savings analysis |
| `GET /api/analytics/cost/free-user-burn` | GET | Free user burn rate |
| `GET /api/analytics/alerts` | GET | Cost anomaly alerts |

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `period` | int | 30 | Analysis period in days |

### Example

```bash
# Get financial dashboard (30 days)
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/analytics/dashboard?period=30

# Get gross margin
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/analytics/gross-margin

# Get cost alerts
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/analytics/alerts
```

## Key Metrics

### Gross Margin

```
Gross Margin % = (Revenue - COGS) / Revenue × 100

COGS = AI Token Cost + Infrastructure Cost - Cache Savings
```

**Targets:**
- Excellent: > 80%
- Good: 70-80%
- Warning: 50-70%
- Critical: < 50%

### Unit Economics

| Metric | Formula | Target |
|--------|---------|--------|
| MRR | Σ(active_sub × plan_price) | Growing |
| ARR | MRR × 12 | Growing |
| ARPU | MRR / active_subscribers | > $20 |
| LTV | ARPU / churn_rate | > $200 |
| Churn Rate | churned / total_subs | < 5% |
| CAC Payback | CAC / ARPU | < 12 months |

### AI Cost Breakdown

| Component | Description |
|-----------|-------------|
| Per-User Cost | Token cost per active user |
| Per-Feature Cost | Cost by agent/feature (ai_chat, ocr, report) |
| Model Comparison | Cost efficiency across models |
| Cache Savings | Savings from prompt caching + context compression |
| Free User Burn | Monthly cost of free-tier users |

## Model Pricing

Configured in `cost_analytics.py.MODEL_PRICING`:

| Model | Input (¢/1K) | Output (¢/1K) |
|-------|-------------|---------------|
| deepseek-chat | 0.14 | 0.28 |
| deepseek-coder | 0.14 | 0.28 |
| deepseek-reasoner | 0.55 | 2.19 |
| gpt-4o | 250.0 | 1000.0 |
| gpt-4o-mini | 15.0 | 60.0 |
| claude-sonnet | 300.0 | 1500.0 |
| claude-haiku | 25.0 | 125.0 |

## Cost Alerts

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| LowGrossMargin | < 50% | critical | Review pricing or reduce costs |
| GrossMarginBelowTarget | < 70% | warning | Optimize token usage |
| HighFreeUserBurn | > $50/month | warning | Review free tier limits |
| HighPerUserCost | > $1/day/user | warning | Check rate limits |
| HighChurnRate | > 10% | warning | Investigate cancellations |
| HighAICostRatio | > 30% of revenue | warning | Optimize AI usage |

## Grafana Dashboard

**UID:** `ai-financial-analytics`

### Panels

| Row | Panels |
|-----|--------|
| Revenue & Margin | MRR, ARR, Gross Margin, ARPU, LTV, Churn Rate |
| Revenue Trend | Daily Revenue, Subscribers by Plan, Payment Success Rate |
| AI Cost Breakdown | Daily AI Cost, Cost by Model, Cost by Feature |
| Unit Economics | Revenue vs Cost/User, Free User Burn, Cache Savings |
| Gross Margin Trend | Gross Margin % (30d), Revenue vs COGS |

## Prometheus Metrics

The cost analytics system exposes these custom metrics:

```
ai_gross_margin_percent          — Current gross margin %
ai_cost_cents_total              — Total AI cost in cents
ai_free_user_monthly_burn_usd    — Free user monthly burn
ai_cache_savings_usd             — Cache savings in USD
ai_unique_users                  — Number of unique AI users
stripe_mrr_cents                 — Monthly recurring revenue
stripe_arpu_cents                — Average revenue per user
stripe_ltv_cents                 — Lifetime value
stripe_churn_rate_percent        — Churn rate
stripe_active_subscribers        — Active subscribers by plan
stripe_revenue_cents             — Total revenue
```

## Integration with Prometheus

Add to `monitoring/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'cost-analytics'
    metrics_path: '/api/analytics/prometheus'
    static_configs:
      - targets: ['backend:5000']
    scrape_interval: 5m
```

## Running the Analysis

```bash
# Via API
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:5000/api/analytics/dashboard?period=30"

# Via Python directly
cd backend
python -c "
from services.cost_analytics import get_financial_dashboard
import json
print(json.dumps(get_financial_dashboard(30), indent=2))
"
```
