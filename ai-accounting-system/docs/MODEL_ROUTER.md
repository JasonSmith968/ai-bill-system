# Intelligent Model Router

## Overview

Automatically selects the optimal AI model based on task type, with cost control, latency optimization, cache-first strategy, and auto-fallback.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Model Router Pipeline                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐ │
│  │  Request  │───▶│   Task       │───▶│   Model Selection     │ │
│  │  + Agent  │    │ Classifier   │    │   (cost/latency/      │ │
│  │  Name     │    │              │    │    reliability score)  │ │
│  └──────────┘    └──────────────┘    └───────────┬───────────┘ │
│                                                   │             │
│  ┌──────────────────────────────────────────────▼───────────┐ │
│  │                    Decision Pipeline                      │ │
│  │                                                          │ │
│  │  1. Cache check ──────────────────────────▶ cache hit?   │ │
│  │  2. Budget check ─────────────────────────▶ over budget? │ │
│  │  3. Model selection (scored)                              │ │
│  │  4. Execute with fallback chain                           │ │
│  │  5. Cache response                                        │ │
│  │  6. Record budget usage                                   │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                    Model Registry                         │ │
│  │                                                          │ │
│  │  deepseek-chat    (tier 1, $0.14/1K, 1.5s)              │ │
│  │  deepseek-coder   (tier 1, $0.14/1K, 1.8s)              │ │
│  │  deepseek-reasoner(tier 3, $0.55/1K, 8.0s)              │ │
│  │  gpt-4o-mini      (tier 2, $15/1K, 2.0s, vision)        │ │
│  │  gpt-4o           (tier 3, $250/1K, 3.0s, vision+tools) │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Usage

### Basic Routing

```python
from services.model_router import get_router

router = get_router()

# Route a request
decision = router.route(
    messages=[{"role": "user", "content": "Analyze my expenses"}],
    agent_name="advisor",
)

print(decision.model)           # "deepseek-reasoner"
print(decision.task_type)       # TaskType.REASONING
print(decision.fallback_chain)  # ["gpt-4o", "deepseek-chat"]
print(decision.estimated_cost_cents)  # 0.0123
```

### Route and Execute (Recommended)

```python
from services.model_router import get_router

router = get_router()

# Route + execute with automatic fallback
response = router.route_and_call(
    messages=[{"role": "user", "content": "Categorize this transaction"}],
    agent_name="categorizer",
    user_id="123",
    request_id="req-abc",
)

print(response["content"])           # LLM response
print(response["_routing"]["model"]) # Selected model
print(response["_cache_hit"])        # False (first call)
```

### With Tool Calling

```python
response = router.route_and_call(
    messages=[{"role": "user", "content": "Calculate tax"}],
    agent_name="tax_agent",
    require_tools=True,  # Only models with tool support
)
```

### With Vision

```python
response = router.route_and_call(
    messages=[{"role": "user", "content": "OCR this receipt"}],
    agent_name="ocr_agent",
    require_vision=True,  # Only vision-capable models
)
```

## Task Classification

Tasks are classified automatically from message content and agent name:

| TaskType | Triggers | Default Model | Fallback |
|----------|----------|---------------|----------|
| SIMPLE | Short messages (< 100 chars) | deepseek-chat | — |
| CHAT | General conversation | deepseek-chat | — |
| ANALYSIS | "trend", "pattern", "统计" | deepseek-chat | deepseek-coder |
| CODE | "code", "function", "debug" | deepseek-coder | deepseek-chat |
| OCR | "receipt", "invoice", "发票" | gpt-4o-mini | deepseek-chat |
| REASONING | "analyze why", "calculate" | deepseek-reasoner | gpt-4o → deepseek-chat |
| REPORT | "report", "summary", "报告" | deepseek-chat | deepseek-coder |
| CATEGORIZE | "categorize", "分类" | deepseek-chat | — |
| EXTRACT | "extract", "parse", "提取" | deepseek-chat | gpt-4o-mini |

## Model Scoring

Models are scored on 4 dimensions (100 points total):

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Cost | 40 pts | Lower cost = higher score |
| Latency | 30 pts | Lower latency = higher score |
| Reliability | 20 pts | Historical success rate |
| Tier | 10 pts | Lower tier (cheaper) preferred |

## Fallback Chain

When a model fails, the router automatically tries the next model:

```
deepseek-reasoner → gpt-4o → deepseek-chat
gpt-4o-mini → deepseek-chat
deepseek-coder → deepseek-chat
```

Fallback triggers:
- HTTP 429 (rate limit)
- HTTP 500/502/503 (server error)
- Timeout
- Connection error
- Circuit breaker OPEN

## Cache Strategy

```
Request → Cache lookup → Hit? → Return cached
                       → Miss? → Route → Execute → Cache → Return
```

- **Key**: SHA256(messages + model)
- **TTL**: 1 hour (configurable)
- **Max size**: 1000 entries
- **Eviction**: LRU (oldest first)

## Budget Control

Per-user daily budget enforcement:

```python
from services.model_router import get_routing_config

config = get_routing_config()
config.max_cost_per_request_cents = 50.0    # $0.50/request
config.max_cost_per_user_daily_cents = 500.0  # $5/user/day
config.budget_check_enabled = True
```

When budget is exceeded:
1. Try cheaper model from fallback chain
2. If no cheaper model available, raise error

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/router/stats` | GET | Router statistics |
| `POST /api/router/classify` | POST | Classify task type |
| `GET /api/router/config` | GET | Get routing config |
| `PUT /api/router/config` | PUT | Update routing config |
| `GET /api/router/models` | GET | List models |
| `PUT /api/router/models/<name>` | PUT | Update model config |
| `GET /api/router/cache` | GET | Cache statistics |
| `DELETE /api/router/cache` | DELETE | Clear cache |
| `GET /api/router/budget/<user_id>` | GET | User budget usage |

## Configuration

```python
from services.model_router import update_routing_config

update_routing_config(
    max_cost_per_request_cents=50.0,
    max_cost_per_user_daily_cents=500.0,
    budget_check_enabled=True,
    prefer_fast_models=True,
    max_acceptable_latency_ms=15000,
    cache_enabled=True,
    cache_ttl_seconds=3600,
    fallback_enabled=True,
    max_fallback_attempts=3,
    force_model=None,  # Set to override all routing
)
```

## Registering Custom Models

```python
from services.model_router import ModelConfig, register_model

register_model(ModelConfig(
    name="my-custom-model",
    provider="custom",
    api_url="https://api.custom.com/v1/chat/completions",
    api_key_env="CUSTOM_API_KEY",
    input_price=0.5,
    output_price=1.0,
    max_context=32768,
    supports_tools=True,
    supports_vision=False,
    avg_latency_ms=2000,
    reliability=0.95,
    tier=2,
))

# Add to task mapping
from services.model_router import _TASK_MODEL_MAP, TaskType
_TASK_MODEL_MAP[TaskType.ANALYSIS].append("my-custom-model")
```

## Integration with Existing Code

The router integrates with existing hardening:

- **Circuit Breaker**: Per-model circuit breaker (existing `get_breaker`)
- **Token Budget**: Pre-request budget check (existing `TokenBudget`)
- **Error Recovery**: Retry with backoff (existing `ErrorRecovery`)
- **LLM Tracer**: Call tracing (existing `get_tracer`)

To use the router in an agent:

```python
from services.model_router import get_router

class MyAgent:
    def run(self, context):
        router = get_router()
        response = router.route_and_call(
            messages=self._build_messages(context),
            agent_name="my_agent",
            user_id=str(context.user_id),
            request_id=context.request_id,
        )
        return response["content"]
```

## Monitoring

### Prometheus Metrics

```
model_router_requests_total{model, task_type}  — Total routed requests
model_router_cache_hits_total                  — Cache hit count
model_router_fallback_total{from, to}          — Fallback events
model_router_budget_rejected_total             — Budget rejection count
```

### Grafana Dashboard

Add panels for:
- Request distribution by model
- Cache hit rate
- Fallback frequency
- Cost per task type
- Budget utilization per user
