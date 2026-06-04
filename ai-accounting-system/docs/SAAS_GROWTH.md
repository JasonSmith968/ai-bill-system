# SaaS Growth System

## Overview

Complete growth engine covering referral, affiliate, onboarding, email lifecycle, retention, and AI usage nudges.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Growth System Architecture                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   Referral    │  │   Affiliate  │  │     Onboarding           │  │
│  │   System      │  │   Tracking   │  │     Flow                 │  │
│  │              │  │              │  │                          │  │
│  │  code gen    │  │  click track │  │  welcome                 │  │
│  │  signup link │  │  conversion  │  │  create_first            │  │
│  │  conversion  │  │  commission  │  │  setup_budget            │  │
│  │  rewards     │  │  payout      │  │  try_ai / invite_team    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
│         │                 │                        │                 │
│         ▼                 ▼                        ▼                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Growth Service                             │  │
│  │                                                              │  │
│  │  generate_referral_code()     track_affiliate_click()        │  │
│  │  process_referral_signup()    process_affiliate_conversion() │  │
│  │  process_referral_conversion()                               │  │
│  │  init_onboarding()            complete_onboarding_step()     │  │
│  │  send_lifecycle_email()       check_retention_actions()      │  │
│  │  check_nudges()               get_growth_dashboard()         │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │                                         │
│         ┌─────────────────┼─────────────────┐                     │
│         ▼                 ▼                 ▼                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  Email        │  │  Retention   │  │  AI Nudge    │            │
│  │  Lifecycle    │  │  Automation  │  │  Engine      │            │
│  │              │  │              │  │              │            │
│  │  8 templates │  │  3d inactive │  │  5 rules     │            │
│  │  queued send │  │  7d inactive │  │  cooldown    │            │
│  │  open/click  │  │  usage limit │  │  max sends   │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Celery Tasks (Beat)                        │  │
│  │                                                              │  │
│  │  send_email_task          — queued email delivery            │  │
│  │  retention_check_task     — daily at 10:00 UTC               │  │
│  │  nudge_check_task         — every 6 hours                    │  │
│  │  init_growth_defaults_task — one-time setup                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Subsystems

### 1. Referral System

Unique referral codes per user. Tracks signup → conversion → reward lifecycle.

**Reward types:** `free_days`, `credits`, `discount_pct`

**Flow:**
1. User A gets referral code (`GET /api/growth/referral/code`)
2. User B registers with code (`POST /api/growth/referral/signup`)
3. User B makes first payment → triggers conversion (`POST /api/growth/referral/convert`)
4. Both users receive configured rewards

**Models:** `Referral`, `InviteReward`

### 2. Affiliate Tracking

Full affiliate partner management with click tracking, cookie-based attribution, and commission payouts.

**Flow:**
1. Affiliate link clicked → `POST /api/growth/affiliate/track` (public, no auth)
2. User converts → `POST /api/growth/affiliate/convert` (admin)
3. Commission calculated and recorded

**Models:** `Affiliate`, `AffiliateClick`, `AffiliateConversion`

### 3. Onboarding Flow

Step-based onboarding with progress tracking. Steps can be completed or skipped.

**Default steps:**
| Step | Title | Optional |
|------|-------|----------|
| `welcome` | Welcome tour | No |
| `create_first` | Create first transaction | No |
| `setup_budget` | Set up budget | Yes |
| `try_ai` | Try AI assistant | Yes |
| `invite_team` | Invite team members | Yes |

**Models:** `OnboardingStep`, `OnboardingFlow`

### 4. Email Lifecycle

8 pre-built email templates with category-based organization.

| Template | Category | Trigger |
|----------|----------|---------|
| `welcome` | onboarding | User signup |
| `onboarding_reminder` | onboarding | Incomplete onboarding |
| `trial_ending` | retention | 3 days before trial end |
| `inactive_3days` | retention | 3 days no activity |
| `inactive_7days` | retention | 7 days no activity |
| `usage_limit_warning` | engagement | 80% of quota used |
| `feature_unlock` | engagement | New feature available |
| `referral_success` | transactional | Referral converted |

**Models:** `EmailTemplate`, `EmailLog`

### 5. Retention Automation

Automated checks for at-risk users.

**Triggers:**
- Inactive 3 days → re-engagement email
- Inactive 7 days → stronger re-engagement email
- Approaching usage limit → warning email

**Celery Beat:** Daily at 10:00 UTC

### 6. AI Usage Nudges

Rule-based nudges to drive feature adoption and engagement.

**Default rules:**
| Rule | Condition | Nudge |
|------|-----------|-------|
| `unused_ai_chat` | AI chat used 0 times, account > 3 days | Try AI assistant |
| `low_ai_usage` | AI calls < 5/week | Explore AI features |
| `no_export` | No exports, account > 7 days | Try export feature |
| `approaching_limit` | > 80% usage | Upgrade prompt |
| `onboarding_incomplete` | Incomplete steps, account > 3 days | Complete setup |

Each rule has `cooldown_hours` (default 72) and `max_sends` (default 3) to prevent spam.

**Models:** `NudgeRule`, `NudgeLog`

### 7. Growth Analytics

Admin dashboard aggregating all growth metrics.

**Metrics:**
- New users by source (organic, referral, affiliate, paid)
- Referral conversion funnel
- Email send/delivery/open rates
- Affiliate click/conversion/revenue
- Nudge effectiveness

## API Endpoints

### Referral
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `GET /api/growth/referral/code` | GET | User | Get/generate referral code |
| `GET /api/growth/referral/stats` | GET | User | Referral statistics |
| `POST /api/growth/referral/signup` | POST | User | Record referral signup |
| `POST /api/growth/referral/convert` | POST | User | Convert referral (first payment) |

### Affiliate
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `POST /api/growth/affiliate/track` | POST | None | Track affiliate click |
| `GET /api/growth/affiliate/stats` | GET | User | Affiliate statistics |
| `POST /api/growth/affiliate/convert` | POST | Admin | Process conversion |

### Onboarding
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `GET /api/growth/onboarding/progress` | GET | User | Get onboarding progress |
| `POST /api/growth/onboarding/complete` | POST | User | Complete/skip step |

### Nudges
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `GET /api/growth/nudges/active` | GET | User | Get active nudges |

### Admin
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `GET /api/growth/admin/dashboard` | GET | Admin | Growth dashboard |
| `POST /api/growth/admin/init` | POST | Admin | Initialize defaults |
| `POST /api/growth/admin/retention/run` | POST | Admin | Manual retention check |
| `POST /api/growth/admin/nudges/run` | POST | Admin | Manual nudge check |

## Celery Beat Schedule

| Task | Schedule | Queue |
|------|----------|-------|
| `retention_check_task` | Daily 10:00 UTC | email |
| `nudge_check_task` | Every 6 hours | email |
| `send_email_task` | On-demand | email |
| `init_growth_defaults_task` | Manual / deploy | email |

## Configuration

### Initialize Defaults

Call once after deployment:

```bash
curl -X POST https://api.example.com/api/growth/admin/init \
  -H "Authorization: Bearer <admin_token>"
```

This creates:
- 8 email templates
- 5 nudge rules

### Custom Email Templates

Templates support `{{variable}}` syntax:

```
Subject: {{user_name}}, 欢迎加入 AI 记账系统
Body: Hi {{user_name}}, your trial ends on {{trial_end_date}}...
```

### Custom Nudge Rules

```json
{
  "name": "custom_rule",
  "trigger_condition": {
    "metric": "feature_x_usage",
    "operator": "eq",
    "value": 0,
    "period_days": 7
  },
  "nudge_type": "in_app",
  "nudge_content": {
    "title": "Try Feature X",
    "message": "Feature X can help you...",
    "cta": "Try Now",
    "cta_url": "/feature-x"
  },
  "cooldown_hours": 168,
  "max_sends": 2
}
```

## Models

### Referral
- `referral_code` — unique per user
- `status` — pending → registered → converted → rewarded
- `reward_type` / `reward_value` — configured via InviteReward

### Affiliate
- `affiliate_code` — unique per partner
- `commission_rate` — percentage (default 20%)
- `cookie_days` — attribution window (default 30)
- Aggregate stats: total_clicks, total_conversions, total_revenue_cents

### GrowthEvent
Tracks all growth-relevant events for analytics:
- `signup`, `invite_sent`, `invite_accepted`
- `upgrade`, `churn`
- `nudge_sent`, `nudge_clicked`

## Integration Points

### Auth Flow
After user registration, call `init_onboarding(user_id)` to create onboarding steps.

### Payment Flow
After first payment, call `process_referral_conversion(user_id)` and `process_affiliate_conversion(user_id, code, revenue)`.

### Dashboard
Embed onboarding progress widget by calling `GET /api/growth/onboarding/progress`.
Show active nudges via `GET /api/growth/nudges/active`.
