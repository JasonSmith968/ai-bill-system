# Retention Analytics

## Overview

6-dimensional retention intelligence: cohort analysis, churn prediction, feature adoption, onboarding completion, referral conversion, and AI engagement scoring.

## Dimensions

### 1. Cohort Analysis

Monthly signup cohorts with retention curves. Shows what percentage of users who signed up in month X are still active in month X+N.

**Data source:** `users.created_at` (cohort anchor), `login_history.login_at` (activity signal)

**Output:**
- Retention matrix: rows = signup month, columns = months since signup
- Month-1 and Month-3 retention rates
- Cohort sizes

**Key metrics:**
- `month1_retention_pct` — % of users who return after 1 month
- `month3_retention_pct` — % of users who return after 3 months

### 2. Churn Prediction

Multi-signal risk scoring (0-100) for each active user.

**Signals:**
| Signal | Max Points | Logic |
|--------|-----------|-------|
| Days since last login | 40 | >30d = 40, >14d = 25, >7d = 10 |
| Login frequency decline | 25 | 0 logins now vs previous = 25 |
| Transaction decline | 20 | 0 tx now vs previous = 20 |
| AI usage decline | 15 | 0 AI now vs previous = 15 |
| Subscription status | 20 | cancelled/expired = 20 |

**Risk levels:**
- `critical` (70+) — immediate intervention needed
- `high` (50-69) — proactive outreach recommended
- `medium` (30-49) — monitor closely
- `low` (<30) — healthy

### 3. Feature Adoption

Percentage of active users who have used each feature.

**Tracked features:**
| Feature | Signal |
|---------|--------|
| 记账 | Any transaction created |
| AI 记账 | `transactions.ai_generated = 1` |
| 票据识别 | `receipt_image` or `ocr_text` present |
| AI 助手 | `agent_execution_logs` entries |
| 报表生成 | `task_records` with type=report |
| 数据导出 | `task_records` with type=export |
| 引导完成 | `onboarding_steps` completed |

### 4. Onboarding Completion

Step-by-step funnel analysis.

**Steps:** welcome → create_first → setup_budget → try_ai → invite_team

**Metrics per step:**
- Completion rate, skip rate, pending rate
- Average time to complete (hours)

**Overall:**
- Full completion rate (all steps)
- Required completion rate (welcome + create_first)

### 5. Referral Conversion

Full referral funnel with viral coefficient.

**Funnel:** code generated → signup → converted → rewarded

**Key metrics:**
- `signup_rate_pct` — referred users who registered
- `conversion_rate_pct` — referred users who paid
- `viral_coefficient` — referred users / total new users
- `referrals_per_referrer` — average referrals per advocate
- Top referrers leaderboard
- Affiliate program stats

### 6. AI Engagement Score

Composite score (0-100) measuring AI feature depth.

**Components:**
| Component | Max Points | Logic |
|-----------|-----------|-------|
| Call volume | 30 | 100+ calls = 30, 50+ = 25, 20+ = 20 |
| Frequency | 25 | 20+ active days = 25, 10+ = 20 |
| Agent breadth | 20 | 5+ agents = 20, 3+ = 15 |
| Success rate | 15 | 95%+ = 15, 85%+ = 10 |
| AI transaction output | 10 | 20+ AI tx = 10, 5+ = 7 |

**Engagement levels:**
- `power_user` (80+) — deeply engaged, high value
- `engaged` (60-79) — regular AI user
- `active` (40-59) — occasional use
- `casual` (20-39) — minimal use
- `dormant` (<20) — at risk of churning

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/retention/dashboard` | GET | Unified dashboard (all 6 dimensions) |
| `GET /api/retention/cohort` | GET | Cohort retention matrix |
| `GET /api/retention/churn` | GET | Churn risk scoring |
| `GET /api/retention/features` | GET | Feature adoption rates |
| `GET /api/retention/onboarding` | GET | Onboarding funnel |
| `GET /api/retention/referral` | GET | Referral conversion funnel |
| `GET /api/retention/ai-engagement` | GET | AI engagement scoring |

**Query parameters:**
- `period` — analysis window in days (default: 30)
- `months` — cohort analysis window in months (default: 12)
- `limit` — max users to return (default: 50)

All endpoints require admin authentication.

## Usage

```bash
# Full dashboard
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/retention/dashboard?period=30

# Cohort analysis (6 months)
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/retention/cohort?months=6

# Churn prediction (top 20 at-risk)
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/retention/churn?limit=20

# Feature adoption (last 30 days)
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/retention/features?period=30

# AI engagement scoring
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/retention/ai-engagement?period=30
```

## Data Flow

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ login_history│   │ transactions │   │ agent_logs   │
│              │   │              │   │              │
│ login_at     │   │ created_at   │   │ created_at   │
│ device_type  │   │ ai_generated │   │ agent_name   │
│ success      │   │ receipt_image│   │ tokens       │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌──────────────────────────────────────────────────────┐
│              Retention Analytics Service              │
│                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Cohort      │  │ Churn       │  │ Feature     │  │
│  │ Analysis    │  │ Prediction  │  │ Adoption    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Onboarding  │  │ Referral    │  │ AI          │  │
│  │ Funnel      │  │ Conversion  │  │ Engagement  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
└──────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  GET /api/retention/dashboard                        │
│  → cohort, churn, features, onboarding, referral, AI │
└──────────────────────────────────────────────────────┘
```
