# Incident Response Runbook

## Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| P0 - Critical | Complete outage | 5 min | Server down, DB unreachable |
| P1 - High | Major feature broken | 15 min | Auth failing, payments broken |
| P2 - Medium | Degraded performance | 1 hour | Slow queries, high latency |
| P3 - Low | Minor issue | 4 hours | UI glitch, non-critical error |

## Incident Response Flow

```
Detect → Triage → Mitigate → Fix → Postmortem
  5m      5m       30m       2h      24h
```

---

## P0: Complete Outage

### Symptoms
- `/health` returns 500 or timeout
- All API endpoints failing
- No metrics being reported

### Diagnosis
```bash
# 1. Check if server process is running
ps aux | grep gunicorn
systemctl status gunicorn

# 2. Check server logs
journalctl -u gunicorn --since "10 minutes ago" --priority=err
tail -50 /var/log/ai-accounting/error.log

# 3. Check database connectivity
mysql -u $DB_USER -p$DB_PASS -h $DB_HOST -e "SELECT 1"

# 4. Check Redis connectivity
redis-cli -h $REDIS_HOST ping

# 5. Check disk space
df -h

# 6. Check memory
free -m
```

### Mitigation
1. Restart application server: `systemctl restart gunicorn`
2. If DB is down: check MySQL service, restart if needed
3. If Redis is down: restart Redis, application should reconnect
4. If disk full: clear logs, rotate old files

---

## P1: Authentication Failure

### Symptoms
- Login returns 401 for valid credentials
- JWT tokens being rejected
- "Unauthorized" errors in logs

### Diagnosis
```bash
# 1. Check JWT secret configuration
grep JWT_SECRET_KEY /opt/ai-accounting/.env.production

# 2. Check token expiry
python -c "import jwt; print(jwt.decode('TOKEN', 'SECRET', algorithms=['HS256']))"

# 3. Check database user table
mysql -e "SELECT id, username, is_locked, failed_login_attempts FROM users LIMIT 5"

# 4. Check rate limiting
redis-cli GET "rate_limit:login:*"
```

### Mitigation
1. If JWT secret changed: restart server with correct secret
2. If users locked: `UPDATE users SET is_locked=0, failed_login_attempts=0 WHERE id=X`
3. If rate limit hit: `redis-cli DEL "rate_limit:*"`

---

## P1: Payment Processing Failure

### Symptoms
- Stripe webhooks failing
- Subscription status not updating
- Payment errors in logs

### Diagnosis
```bash
# 1. Check Stripe webhook endpoint
curl -sf https://api.stripe.com/v1/webhook_endpoints \
  -u $STRIPE_SECRET_KEY:

# 2. Check webhook events
mysql -e "SELECT * FROM processed_events ORDER BY created_at DESC LIMIT 10"

# 3. Check Stripe signature verification
grep "Stripe-Signature" /var/log/ai-accounting/access.log | tail -5

# 4. Check subscription status
mysql -e "SELECT id, status, stripe_subscription_id FROM subscriptions WHERE status='past_due'"
```

### Mitigation
1. If webhook secret wrong: update `STRIPE_WEBHOOK_SECRET` in .env
2. If signature failing: verify webhook secret matches Stripe dashboard
3. If subscription stuck: manually sync from Stripe API
4. Retry failed events: `stripe events resend evt_XXX`

---

## P2: Slow Performance

### Symptoms
- p95 latency > 2s
- Users reporting slowness
- High CPU or memory usage

### Diagnosis
```bash
# 1. Check system resources
top -bn1 | head -20
iostat -x 1 3

# 2. Check database slow queries
mysql -e "SHOW PROCESSLIST"
mysql -e "SHOW ENGINE INNODB STATUS\G" | grep -A5 "ROW OPERATIONS"

# 3. Check connection pool
curl -sf http://localhost:5000/metrics -H "Authorization: Bearer $METRICS_TOKEN" | grep db_pool

# 4. Check Redis memory
redis-cli INFO memory

# 5. Check for lock contention
mysql -e "SELECT * FROM information_schema.INNODB_LOCKS"
```

### Mitigation
1. If CPU high: check for runaway queries, increase workers
2. If memory high: check for memory leaks, restart workers
3. If DB slow: check indexes, optimize queries
4. If Redis full: increase maxmemory or clear old keys

---

## P2: High Error Rate

### Symptoms
- Error rate > 1% in monitoring
- 500 errors in logs
- Sentry alerting

### Diagnosis
```bash
# 1. Check error logs
tail -100 /var/log/ai-accounting/error.log | grep ERROR

# 2. Check Sentry for specific errors
# Visit: https://sentry.io/organizations/YOUR_ORG/issues/

# 3. Check for specific error patterns
grep "ObjectDeletedError" /var/log/ai-accounting/error.log | wc -l
grep "IntegrityError" /var/log/ai-accounting/error.log | wc -l
grep "TimeoutError" /var/log/ai-accounting/error.log | wc -l

# 4. Check recent deployments
git log --oneline -5
```

### Mitigation
1. If specific error pattern: apply targeted fix
2. If widespread: rollback to last known good version
3. If data issue: check database integrity
4. If external service: check circuit breaker status

---

## P3: Data Inconsistency

### Symptoms
- User reports incorrect balances
- Dashboard numbers don't match
- Missing transactions

### Diagnosis
```bash
# 1. Check transaction totals
mysql -e "
  SELECT user_id, type, SUM(amount) as total, COUNT(*) as count
  FROM transactions
  WHERE user_id = X
  GROUP BY user_id, type
"

# 2. Check for orphaned records
mysql -e "
  SELECT t.id, t.category_id
  FROM transactions t
  LEFT JOIN categories c ON t.category_id = c.id
  WHERE c.id IS NULL AND t.category_id IS NOT NULL
"

# 3. Check tenant isolation
mysql -e "
  SELECT t.id, t.tenant_id, u.tenant_id as user_tenant
  FROM transactions t
  JOIN users u ON t.user_id = u.id
  WHERE t.tenant_id != u.tenant_id
"
```

### Mitigation
1. If calculation error: recalculate from source data
2. If orphaned records: reassign or delete
3. If tenant isolation breach: investigate and fix

---

## Communication Templates

### Initial Acknowledgment
```
[INCIDENT] We are aware of issues with [SERVICE]. 
Our team is investigating. Updates every 15 minutes.
ETA for resolution: [TIME]
```

### Status Update
```
[UPDATE] Root cause identified: [CAUSE]
Current status: [MITIGATING/FIXING/MONITORING]
ETA: [TIME]
```

### Resolution
```
[RESOLVED] The incident affecting [SERVICE] has been resolved.
Duration: [TIME]
Root cause: [CAUSE]
Postmortem: [LINK]
```

---

## Escalation Matrix

| Time Elapsed | Action |
|--------------|--------|
| 0 min | On-call engineer responds |
| 15 min | Escalate to Tech Lead |
| 30 min | Escalate to Engineering Manager |
| 1 hour | Escalate to VP Engineering |
| 2 hours | All-hands incident call |
