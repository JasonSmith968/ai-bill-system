# Production Operations Runbook

## Quick Reference

| Service | Port | Health Check | Restart |
|---------|------|-------------|---------|
| Backend | 5000 | `curl localhost:5000/health` | `docker compose restart backend` |
| MySQL | 3306 | `docker inspect ai-mysql --format='{{.State.Health.Status}}'` | `docker compose restart mysql` |
| Redis | 6379 | `docker exec ai-redis redis-cli ping` | `docker compose restart redis` |
| Celery Worker | — | `docker logs ai-celery-worker --tail 5` | `docker compose restart celery-worker` |
| Celery Beat | — | `docker logs ai-celery-beat --tail 5` | `docker compose restart celery-beat` |
| Nginx | 80/443 | `curl -I localhost` | `docker compose restart nginx` |
| Prometheus | 9090 | `curl localhost:9090/-/healthy` | `docker compose restart prometheus` |
| Grafana | 3000 | `curl localhost:3000/api/health` | `docker compose restart grafana` |
| Elasticsearch | 9200 | `curl localhost:9200/_cluster/health` | `docker compose restart elasticsearch` |
| Kibana | 5601 | `curl localhost:5601/api/status` | `docker compose restart kibana` |

## Common Operations

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend --tail 100

# Errors only
docker compose -f docker-compose.prod.yml logs backend 2>&1 | grep -i error
```

### Restart a Service

```bash
# Single service
docker compose -f docker-compose.prod.yml restart backend

# All services
docker compose -f docker-compose.prod.yml restart
```

### Scale Celery Workers

```bash
docker compose -f docker-compose.prod.yml up -d --scale celery-worker=3
```

### Database Operations

```bash
# Connect to MySQL
docker exec -it ai-mysql mysql -u ai_user -p ai_accounting

# Run migration
docker exec ai-backend flask db upgrade

# Create backup
./scripts/backup.sh

# Validate backup
./scripts/backup_validate.sh
```

### Secret Rotation

```bash
# Rotate single secret
python scripts/generate_secrets.py --rotate SECRET_KEY

# Validate all secrets
python scripts/validate_secrets.py

# Regenerate all (DANGEROUS — overwrites existing)
python scripts/generate_secrets.py --force
```

### SSL Certificate Renewal

```bash
# Manual renewal
certbot renew

# Check expiry
openssl x509 -enddate -noout -in nginx/ssl/fullchain.pem

# Auto-renewal is configured via cron: /etc/cron.d/certbot-renewal
```

## Incident Response

### Service Down

1. Check container status: `docker compose ps`
2. Check logs: `docker compose logs <service> --tail 50`
3. Restart: `docker compose restart <service>`
4. If persistent, check resource usage: `docker stats`

### High Memory Usage

```bash
# Check container memory
docker stats --no-stream

# Restart memory-heavy service
docker compose restart backend

# If MySQL is the issue
docker exec ai-mysql mysql -u root -p -e "SHOW PROCESSLIST;"
docker exec ai-mysql mysql -u root -p -e "SHOW ENGINE INNODB STATUS\G"
```

### Database Connection Issues

```bash
# Check MySQL health
docker inspect ai-mysql --format='{{.State.Health.Status}}'

# Check connection pool
docker exec ai-backend python -c "
from extensions import db
from app import create_app
app = create_app('production')
with app.app_context():
    result = db.session.execute('SELECT 1')
    print('DB OK:', result.scalar())
"

# Check active connections
docker exec ai-mysql mysql -u root -p -e "SHOW STATUS LIKE 'Threads_connected';"
```

### Redis Issues

```bash
# Check Redis health
docker exec ai-redis redis-cli -a "$REDIS_PASSWORD" ping

# Check memory usage
docker exec ai-redis redis-cli -a "$REDIS_PASSWORD" info memory

# Check connected clients
docker exec ai-redis redis-cli -a "$REDIS_PASSWORD" info clients
```

### Celery Queue Backlog

```bash
# Check queue lengths
docker exec ai-redis redis-cli -a "$REDIS_PASSWORD" llen ai
docker exec ai-redis redis-cli -a "$REDIS_PASSWORD" llen email
docker exec ai-redis redis-cli -a "$REDIS_PASSWORD" llen ocr

# Check active tasks
docker exec ai-celery-worker celery -A celery_app.celery inspect active

# Check reserved tasks
docker exec ai-celery-worker celery -A celery_app.celery inspect reserved
```

### SSL/TLS Issues

```bash
# Check certificate validity
openssl s_client -connect localhost:443 -servername your-domain.com

# Check certificate expiry
openssl x509 -enddate -noout -in nginx/ssl/fullchain.pem

# Regenerate self-signed (emergency)
openssl req -x509 -nodes -days 30 \
    -newkey rsa:2048 \
    -keyout nginx/ssl/privkey.pem \
    -out nginx/ssl/fullchain.pem \
    -subj "/CN=your-domain.com"
docker exec ai-nginx nginx -s reload
```

## Monitoring

### Grafana Dashboards

- **Production Monitoring**: System overview, infrastructure, Celery, AI/LLM
- **Financial Analytics**: Revenue, margin, cost breakdown, unit economics

Access: `ssh -L 3000:localhost:3000 root@your-server` then open `http://localhost:3000`

### Prometheus Queries

```promql
# Request rate
rate(flask_request_total[5m])

# Error rate
rate(flask_request_total{status=~"5.."}[5m]) / rate(flask_request_total[5m])

# Request latency P95
histogram_quantile(0.95, rate(flask_request_duration_seconds_bucket[5m]))

# Celery task rate
rate(celery_task_total[5m])
```

### Kibana

Access: `ssh -L 5601:localhost:5601 root@your-server` then open `http://localhost:5601`

## Emergency Procedures

### Full Service Restart

```bash
docker compose -f docker-compose.prod.yml down --timeout 30
docker compose -f docker-compose.prod.yml up -d
```

### Rollback to Previous Version

```bash
./deploy/deploy.sh --rollback
```

### Emergency Maintenance Mode

```bash
# Create maintenance page
echo '<html><body><h1>Maintenance in Progress</h1><p>Please try again later.</p></body></html>' > /tmp/maintenance.html

# Redirect nginx to maintenance page
docker exec ai-nginx cp /tmp/maintenance.html /usr/share/nginx/html/index.html
docker exec ai-nginx nginx -s reload

# ... perform maintenance ...

# Restore normal operation
docker compose -f docker-compose.prod.yml restart nginx
```

## Backup Schedule

| Backup | Frequency | Retention | Location |
|--------|-----------|-----------|----------|
| MySQL full | Daily 3:00 | 7 days | `backups/` |
| Redis AOF | Continuous | — | Docker volume |
| Uploads | Daily | 30 days | `backups/uploads_*.tar.gz` |
| Config | On change | Git | Git repository |

## Contact Escalation

1. Check this runbook
2. Check monitoring dashboards (Grafana)
3. Check logs (Kibana / `docker compose logs`)
4. Check error tracking (Sentry, if configured)
5. Escalate to on-call engineer
