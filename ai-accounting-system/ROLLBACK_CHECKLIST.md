# Rollback Checklist

## When to Rollback

- Error rate > 5% sustained for 5 minutes
- p95 latency > 5s sustained for 5 minutes
- Database connection pool exhausted
- Critical security vulnerability actively exploited
- Data corruption detected
- Complete service outage

## Rollback Procedure

### Phase 1: Immediate (0-2 min)

1. **Stop traffic to new version**
   ```bash
   # Nginx: switch upstream to maintenance page
   sudo cp /etc/nginx/sites-available/maintenance /etc/nginx/sites-enabled/default
   sudo nginx -t && sudo systemctl reload nginx
   ```

2. **Stop application server**
   ```bash
   sudo systemctl stop gunicorn
   # Or kill processes
   pkill -f "gunicorn.*app:create_app"
   ```

3. **Stop Celery workers**
   ```bash
   pkill -f "celery.*worker"
   pkill -f "celery.*beat"
   ```

### Phase 2: Code Rollback (2-5 min)

4. **Checkout previous version**
   ```bash
   cd /opt/ai-accounting
   git log --oneline -5  # identify last good commit
   git checkout <LAST_GOOD_COMMIT>
   ```

5. **Restore dependencies**
   ```bash
   pip install -r requirements.txt
   ```

6. **Database rollback (if needed)**
   ```bash
   # Only if migration was applied
   flask db downgrade
   # Or restore from backup
   mysql -u root ai_accounting < /backups/pre_deploy_YYYYMMDD.sql
   ```

### Phase 3: Restart (5-8 min)

7. **Start application server**
   ```bash
   gunicorn -c gunicorn.conf.py "app:create_app()"
   ```

8. **Start Celery workers**
   ```bash
   celery -A celery_app worker --loglevel=info --concurrency=4 &
   celery -A celery_app beat &
   ```

9. **Restore traffic**
   ```bash
   sudo cp /etc/nginx/sites-available/production /etc/nginx/sites-enabled/default
   sudo nginx -t && sudo systemctl reload nginx
   ```

### Phase 4: Verification (8-15 min)

10. **Health check**
    ```bash
    curl -sf http://localhost:5000/health
    # Expected: {"status": "ok", "timestamp": "..."}
    ```

11. **Smoke test**
    ```bash
    # Login
    TOKEN=$(curl -sf http://localhost:5000/api/auth/login \
      -H "Content-Type: application/json" \
      -d '{"username":"admin","password":"***"}' | jq -r .access_token)
    
    # Transactions
    curl -sf http://localhost:5000/api/transactions?page=1 \
      -H "Authorization: Bearer $TOKEN" | jq .total
    
    # Dashboard
    curl -sf http://localhost:5000/api/dashboard/summary \
      -H "Authorization: Bearer $TOKEN" | jq .total_expense
    ```

12. **Check logs for errors**
    ```bash
    tail -100 /var/log/ai-accounting/error.log
    journalctl -u gunicorn --since "5 minutes ago" --priority=err
    ```

13. **Monitor for 15 minutes**
    - Error rate returning to baseline
    - Latency returning to baseline
    - No new error spikes

## Post-Rollback

- [ ] Incident report written
- [ ] Root cause identified
- [ ] Fix developed and tested
- [ ] Re-deployment scheduled
- [ ] Team notified of rollback and next steps

## Database-Specific Rollback

If the issue is database-related:

1. **Stop all application servers** (prevent further writes)
2. **Assess damage**: `SELECT COUNT(*) FROM transactions WHERE updated_at > '<deploy_time>'`
3. **Point-in-time recovery**: Use MySQL binlog or backup
4. **Restore**: `mysql -u root ai_accounting < /backups/pre_deploy.sql`
5. **Verify data integrity**: Run consistency checks
6. **Restart application servers**

## Emergency Contacts

| Role | Contact | When |
|------|---------|------|
| On-call Engineer | [PHONE] | First responder |
| Tech Lead | [PHONE] | Escalation |
| DBA | [PHONE] | Database issues |
| DevOps | [PHONE] | Infrastructure issues |
