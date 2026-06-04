# AI Cost Control System

## Overview

Unified guardrail system ensuring positive gross margin as user base grows. Integrates free tier enforcement, per-user budgets, anomaly detection, cache/compression/routing optimization tracking.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AI Cost Control Pipeline                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌───────────────┐    ┌──────────────────────────┐  │
│  │  Request  │───▶│  Guardrail    │───▶│  LLM Call                │  │
│  │           │    │               │    │                          │  │
│  │  user_id  │    │ 1. Plan check │    │  circuit_breaker         │  │
│  │  plan     │    │ 2. Token est  │    │  token_budget            │  │
│  │  messages │    │ 3. Cost est   │    │  error_recovery          │  │
│  └──────────┘    │ 4. Budget chk │    │  tracer                  │  │
│                  └───────┬───────┘    └─────────────┬────────────┘  │
│                          │                          │                │
│                          ▼                          ▼                │
│                  ┌───────────────┐    ┌──────────────────────────┐  │
│                  │  Denied       │    │  Post-Request            │  │
│                  │  (HTTP 429)   │    │                          │  │
│                  └───────────────┘    │  1. Record tokens        │  │
│                                      │  2. Record cost           │  │
│                                      │  3. Anomaly detection     │  │
│                                      │  4. Cache stats           │  │
│                                      │  5. Compression stats     │  │
│                                      │  6. Routing savings       │  │
│                                      └──────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Cost Control Service                       │  │
│  │                                                              │  │
│  │  UsageTracker        — per-user daily counters               │  │
│  │  AnomalyDetector     — spending spike detection              │  │
│  │  CostControlConfig   — plan limits + thresholds              │  │
│  │                                                              │  │
│  │  check_request_allowed()  — pre-request guardrail            │  │
│  │  record_usage()           — post-request recording           │  │
│  │  get_user_cost_report()   — per-user cost breakdown          │  │
│  │  get_cost_dashboard()     — global cost dashboard            │  │
│  │  get_optimization_recommendations()  — actionable tips       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

## 8 Control Dimensions

### 1. Token Cost Statistics

Tracked per-user per-day:
- Input tokens, output tokens, total tokens
- Cost in cents (calculated from model pricing)
- Requests count

View: `GET /api/cost-control/my-usage`

### 2. User Cost Ranking

Admin dashboard shows top 20 cost users with:
- Request count, token usage, cost
- Cache hit rate per user

View: `GET /api/cost-control/admin/dashboard`

### 3. Free User Quota

Enforced limits per plan tier:

| Tier | Daily Requests | Daily Tokens | Daily Cost | Monthly Cost |
|------|---------------|-------------|-----------|-------------|
| Free | 50 | 100,000 | $0.10 | $2.00 |
| Starter | 200 | 500,000 | $0.50 | $10.00 |
| Pro | 1,000 | 2,000,000 | $2.00 | $50.00 |
| Enterprise | 5,000 | 10,000,000 | $10.00 | $250.00 |

Check: `POST /api/cost-control/my-check`

### 4. Cache Hit Rate

Tracked per-user and globally:
- Cache hits vs misses
- Hit rate percentage
- Estimated savings from cache

Integrated with `ResponseCache` in model router.

### 5. Prompt Compression

Tracked savings from `ContextCompressor`:
- Tokens saved by compression
- Estimated cost savings

Integrated with `ContextCompressor.compress()`.

### 6. Model Routing

Tracked savings from intelligent routing:
- Cost difference between selected model vs premium model
- Routing decisions logged

Integrated with `ModelRouter.route()`.

### 7. Budget Guardrail

Pre-request check pipeline:
```
Request → Plan lookup → Daily request limit check
                      → Daily token limit check
                      → Daily cost limit check
                      → Allowed / Denied (HTTP 429)
```

Integrated into `LLMClient.chat()` — every LLM call is guarded.

### 8. Anomaly Detection

Two-level detection:
- **Per-user spike**: Current cost > 3x user's historical average
- **Global spike**: Recent average > 3x historical average

Alerts emitted via logger + optional webhook.

## API Endpoints

### User Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `GET /api/cost-control/my-usage` | GET | User | Today's usage and limits |
| `POST /api/cost-control/my-check` | POST | User | Pre-request budget check |

### Admin Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `GET /api/cost-control/admin/dashboard` | GET | Admin | Global cost dashboard |
| `GET /api/cost-control/admin/user/<id>` | GET | Admin | Per-user cost report |
| `GET /api/cost-control/admin/recommendations` | GET | Admin | Optimization tips |
| `GET /api/cost-control/admin/anomaly` | GET | Admin | Anomaly check |
| `GET /api/cost-control/admin/config` | GET | Admin | Current config |
| `PUT /api/cost-control/admin/config` | PUT | Admin | Update config |

## Integration Points

### LLM Client (`services/llm_client.py`)

Every `chat()` call goes through:
1. Circuit breaker check
2. Token budget check
3. **Cost control guardrail** (new)
4. LLM call with retry/fallback
5. Post-call: record to circuit breaker, budget, tracer, **cost control**

### Agent Manager (`agents/manager.py`)

Token extraction improved:
1. Check `_tokens_used` on context
2. Fall back to LLM tracer stats
3. Fall back to token budget usage
4. Record to billing service

### Model Router (`services/model_router.py`)

Cost savings tracked:
- When routing selects a cheaper model, the savings are recorded
- Cache hits are recorded

### Context Compressor (`agents/context_compressor.py`)

Compression savings tracked:
- Tokens saved by compression are recorded
- Used for optimization recommendations

## Configuration

### Update Plan Limits

```bash
curl -X PUT https://api.example.com/api/cost-control/admin/config \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "free_tier": {"daily_requests": 100, "daily_cost_cents": 20},
    "anomaly_spike_multiplier": 5.0
  }'
```

### Environment Variables

No additional env vars required. Uses existing:
- `DEEPSEEK_API_KEY` — for LLM calls
- Model pricing from `cost_analytics.MODEL_PRICING`

## Monitoring

### Grafana Panels

Add to existing dashboard:
- Cost control guardrail denials (counter)
- Per-tier usage distribution
- Cache hit rate trend
- Anomaly detection alerts
- Top cost users table

### Prometheus Metrics

```
cost_control_requests_total{user_id, plan, status}  — allowed/denied
cost_control_cost_cents{user_id}                     — recorded cost
cost_control_anomalies_total{type}                   — anomaly count
cost_control_cache_hit_rate                          — global hit rate
```

## Cost Optimization Loop

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Monitor   │────▶│   Analyze   │────▶│   Optimize  │
│             │     │             │     │             │
│ Track usage │     │ Find waste  │     │ Apply fixes │
│ Track cost  │     │ Detect spike│     │ Tune limits │
│ Track cache │     │ Rank users  │     │ Route smart │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                                       │
       └───────────────────────────────────────┘
```

1. **Monitor**: Every AI request records tokens, cost, cache, compression
2. **Analyze**: Dashboard shows per-user cost, cache rate, anomalies
3. **Optimize**: Recommendations suggest cache tuning, routing adjustments
4. **Enforce**: Guardrail blocks requests exceeding plan limits
