# Production Deployment Checklist

## Pre-Deploy (T-24h)

- [ ] All code merged to `main` branch
- [ ] All tests passing (unit, integration, chaos)
- [ ] Load test results reviewed and accepted
- [ ] Security scan completed — no critical/high CVEs
- [ ] Dependency audit completed — all packages pinned
- [ ] Database migration tested on staging
- [ ] Backup of production database created
- [ ] Rollback plan reviewed and tested
- [ ] Team notified of deployment window
- [ ] Monitoring dashboards open and baseline captured

## Environment Configuration (T-1h)

- [ ] `.env.production` created from `.env.production.example`
- [ ] `SECRET_KEY` — 64+ char random string
- [ ] `JWT_SECRET_KEY` — 64+ char random string
- [ ] `DATABASE_URL` — MySQL connection string with SSL
- [ ] `REDIS_URL` — Redis connection string
- [ ] `DEEPSEEK_API_KEY` — valid API key with sufficient quota
- [ ] `STRIPE_SECRET_KEY` — live mode key (not test)
- [ ] `STRIPE_WEBHOOK_SECRET` — live webhook signing secret
- [ ] `CORS_ORIGINS` — production domain only (no localhost)
- [ ] `SENTRY_DSN` — production project DSN
- [ ] `FERNET_KEY` — encryption key for credentials
- [ ] `METRICS_AUTH_TOKEN` — strong random token
- [ ] `FLASK_ENV=production`
- [ ] `DEBUG=False` confirmed
- [ ] `LOG_LEVEL=WARNING` (or INFO for initial launch)

## Database (T-30m)

- [ ] MySQL 8.0+ running and accessible
- [ ] Database created with `utf8mb4` charset
- [ ] Database user created with minimal permissions
- [ ] Connection pool settings: `pool_size=20`, `pool_recycle=1800`, `pool_pre_ping=True`
- [ ] `flask db upgrade` run successfully
- [ ] Seed data loaded (roles, permissions, plans, default categories)
- [ ] Database backup completed and verified

## Redis (T-30m)

- [ ] Redis 7.0+ running and accessible
- [ ] Redis password set (if not using socket auth)
- [ ] Maxmemory policy set to `allkeys-lru`
- [ ] Redis persistence enabled (AOF + RDB)

## Application Server (T-15m)

- [ ] Gunicorn installed: `pip install gunicorn`
- [ ] Gunicorn config:
  ```
  workers = 4 * CPU_CORES + 1
  worker_class = 'gevent'
  worker_connections = 1000
  timeout = 120
  keepalive = 5
  max_requests = 1000
  max_requests_jitter = 50
  ```
- [ ] Health check endpoint responding: `GET /health`
- [ ] Prometheus metrics secured: `GET /metrics` requires Bearer token

## Celery Workers (T-15m)

- [ ] Celery workers running: `celery -A celery_app worker --loglevel=info --concurrency=4`
- [ ] Celery beat running (if scheduled tasks): `celery -A celery_app beat`
- [ ] Task queue monitored

## Reverse Proxy / Load Balancer (T-15m)

- [ ] Nginx/Caddy configured with:
  - [ ] SSL/TLS termination (Let's Encrypt or cloud cert)
  - [ ] `proxy_pass` to Gunicorn
  - [ ] `client_max_body_size 16M` (for file uploads)
  - [ ] Rate limiting headers
  - [ ] Security headers (HSTS, X-Frame-Options, etc.)
  - [ ] gzip compression
  - [ ] Static file serving bypass for API routes

## Post-Deploy Verification (T+5m)

- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] User login flow works end-to-end
- [ ] Transaction CRUD works
- [ ] Dashboard loads with data
- [ ] AI chat responds (if LLM key configured)
- [ ] WebSocket connects successfully
- [ ] Stripe webhook receives test event
- [ ] Prometheus metrics accessible
- [ ] Sentry receiving errors (trigger test error)
- [ ] Log files being written

## Monitoring Active (T+15m)

- [ ] CPU usage < 70%
- [ ] Memory usage < 80%
- [ ] Error rate < 1%
- [ ] p95 latency < 1s
- [ ] Database connection pool not exhausted
- [ ] Redis memory usage normal
- [ ] Celery queue length stable

## Sign-Off

- [ ] All post-deploy checks passed
- [ ] No critical errors in logs
- [ ] Team notified of successful deployment
- [ ] Monitoring on-watch rotation confirmed
