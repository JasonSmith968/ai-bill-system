# Backup & Restore Validation

## Backup Strategy

### Database Backup

| Type | Frequency | Retention | Method |
|------|-----------|-----------|--------|
| Full backup | Daily 2:00 AM | 30 days | `mysqldump` |
| Incremental | Every 6 hours | 7 days | MySQL binlog |
| Pre-deploy | Before each deploy | 90 days | Manual `mysqldump` |

### Backup Commands

```bash
# Full backup
mysqldump -u backup_user -p --single-transaction --routines --triggers \
  ai_accounting | gzip > /backups/ai_accounting_$(date +%Y%m%d_%H%M%S).sql.gz

# Pre-deploy backup
mysqldump -u backup_user -p --single-transaction --routines --triggers \
  ai_accounting > /backups/pre_deploy_$(date +%Y%m%d_%H%M%S).sql

# Verify backup integrity
gunzip -t /backups/ai_accounting_*.sql.gz && echo "Backup OK"
```

### File Backup

| Item | Location | Frequency |
|------|----------|-----------|
| Uploads | `/opt/ai-accounting/uploads/` | Daily (rsync) |
| Logs | `/var/log/ai-accounting/` | Weekly rotation |
| Config | `/opt/ai-accounting/.env.production` | With each change |
| SSL certs | `/etc/letsencrypt/` | With renewal |

## Restore Procedures

### Full Database Restore

```bash
# 1. Stop application
sudo systemctl stop gunicorn
pkill -f celery

# 2. Drop and recreate database
mysql -u root -e "DROP DATABASE ai_accounting; CREATE DATABASE ai_accounting CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 3. Restore from backup
gunzip -c /backups/ai_accounting_YYYYMMDD.sql.gz | mysql -u root ai_accounting

# 4. Verify restoration
mysql -u root ai_accounting -e "
  SELECT 'users' as tbl, COUNT(*) as cnt FROM users
  UNION ALL
  SELECT 'transactions', COUNT(*) FROM transactions
  UNION ALL
  SELECT 'categories', COUNT(*) FROM categories;
"

# 5. Restart application
sudo systemctl start gunicorn
celery -A celery_app worker --loglevel=info &
```

### Point-in-Time Recovery

```bash
# 1. Stop application
sudo systemctl stop gunicorn

# 2. Restore last full backup
gunzip -c /backups/ai_accounting_YYYYMMDD.sql.gz | mysql -u root ai_accounting

# 3. Apply binlog up to specific time
mysqlbinlog --stop-datetime="2026-05-28 14:30:00" \
  /var/lib/mysql/binlog.000042 | mysql -u root ai_accounting

# 4. Verify data
mysql -u root ai_accounting -e "SELECT MAX(updated_at) FROM transactions;"

# 5. Restart application
sudo systemctl start gunicorn
```

## Validation Checklist

### Weekly Backup Validation

- [ ] Backup file exists and is non-empty
- [ ] Backup file passes integrity check (`gunzip -t`)
- [ ] Backup size is reasonable (within 20% of previous)
- [ ] Test restore to staging database succeeds
- [ ] Row counts match between production and restored
- [ ] Critical queries return expected results on restored DB

### Monthly Restore Drill

- [ ] Full restore completed within RTO (30 min)
- [ ] All tables present and populated
- [ ] Application starts successfully against restored DB
- [ ] Login flow works
- [ ] Transaction data is intact
- [ ] No orphaned records
- [ ] Tenant isolation maintained

### Pre-Deploy Backup

- [ ] Backup created before deployment
- [ ] Backup stored in separate location from production
- [ ] Backup verified (size, integrity)
- [ ] Restore procedure documented and tested
- [ ] Rollback plan references this specific backup

## Recovery Time Objectives

| Scenario | RTO | RPO | Method |
|----------|-----|-----|--------|
| Server failure | 15 min | 0 | Failover to standby |
| Database corruption | 30 min | 6 hours | Restore from backup |
| Accidental deletion | 1 hour | 6 hours | Point-in-time recovery |
| Ransomware | 4 hours | 24 hours | Restore from offsite backup |

## Backup Monitoring

```bash
# Check backup age
find /backups -name "ai_accounting_*.sql.gz" -mtime +1 && echo "WARNING: Backup older than 24h"

# Check backup size trend
ls -lhS /backups/ai_accounting_*.sql.gz | head -7

# Alert if backup missing
if [ ! -f "/backups/ai_accounting_$(date +%Y%m%d)*.sql.gz" ]; then
  echo "ALERT: No backup found for today" | mail -s "Backup Alert" ops@company.com
fi
```

## Storage Locations

| Location | Purpose | Encryption | Access |
|----------|---------|------------|--------|
| Local `/backups/` | Recent backups | At rest | root only |
| S3/OSS bucket | Long-term archive | AES-256 | IAM role |
| Offsite replica | Disaster recovery | AES-256 | VPN only |
