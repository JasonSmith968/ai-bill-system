# Production Deployment Guide

## Prerequisites

- Ubuntu 24.04 LTS VPS (minimum: 2 vCPU, 4GB RAM, 40GB SSD)
- Domain name with DNS A record pointing to server IP
- Root or sudo access
- SSH key pair for authentication

## Quick Start (First Deployment)

```bash
# 1. SSH into your server
ssh root@YOUR_SERVER_IP

# 2. Clone the repository
git clone https://github.com/your-org/ai-accounting-system.git
cd ai-accounting-system

# 3. Run server hardening (one-time)
sudo bash deploy/harden.sh --ssh-port 2222 --admin-ip YOUR_HOME_IP

# 4. Generate production secrets
python scripts/generate_secrets.py --force

# 5. Edit .env.production with your settings
#    - Set DEEPSEEK_API_KEY
#    - Set CORS_ORIGINS to your domain
#    - Set SENTRY_DSN (optional)
#    - Review all generated values

# 6. Deploy
bash deploy/deploy.sh --domain ai.example.com --email admin@example.com

# 7. Verify
bash deploy/verify.sh https://ai.example.com
```

## File Structure

```
deploy/
├── deploy.sh          # Main deployment script
├── harden.sh          # Server hardening (run once)
├── verify.sh          # Post-deploy verification
├── DEPLOYMENT.md      # This file
└── logs/              # Deployment logs (auto-generated)
```

## Deployment Script Options

```
Usage: deploy.sh [OPTIONS]

Options:
  --domain DOMAIN       Production domain name (for SSL)
  --email EMAIL         Email for Let's Encrypt certificate
  --dry-run             Show what would be done without executing
  --skip-ssl            Skip SSL certificate setup
  --skip-build          Skip Docker image build (use existing)
  --skip-migrate        Skip database migrations
  --force               Force deployment even with warnings
  --rollback            Rollback to previous version
  -v, --verbose         Enable verbose output
  -h, --help            Show help
```

## Server Hardening Options

```
Usage: harden.sh [OPTIONS]

Options:
  --ssh-port PORT       Custom SSH port (default: 22)
  --admin-ip IP         IP address for monitoring access
  --dry-run             Show what would be done
```

## SSL Certificates

### Let's Encrypt (Recommended)

The deploy script automatically requests certificates if:
- `--domain` is specified
- `certbot` is installed
- Domain resolves to the server

Install certbot:
```bash
apt install certbot
```

### Manual Certificate

Place your certificates in `nginx/ssl/`:
```
nginx/ssl/fullchain.pem    # Certificate + intermediate chain
nginx/ssl/privkey.pem      # Private key
```

### Auto-Renewal

```bash
# Add cron job for Let's Encrypt renewal
echo "0 3 * * * certbot renew --quiet --deploy-hook 'docker restart ai-nginx'" | crontab -
```

## Updating the Application

```bash
# Pull latest code
git pull

# Redeploy (skip SSL since certs exist)
bash deploy/deploy.sh --skip-ssl --domain ai.example.com
```

## Rollback

```bash
# Rollback to previous commit
bash deploy/deploy.sh --rollback
```

## Monitoring Access

Monitoring services are bound to `127.0.0.1` and not exposed externally. Access via SSH tunnel:

```bash
# Prometheus
ssh -L 9090:localhost:9090 root@YOUR_SERVER_IP
# Open http://localhost:9090

# Grafana
ssh -L 3000:localhost:3000 root@YOUR_SERVER_IP
# Open http://localhost:3000 (admin / see GRAFANA_PASSWORD in .env.production)

# Kibana
ssh -L 5601:localhost:5601 root@YOUR_SERVER_IP
# Open http://localhost:5601
```

## Service Management

```bash
# View all services
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f --tail=100

# Restart a single service
docker compose -f docker-compose.prod.yml restart backend

# Restart all
docker compose -f docker-compose.prod.yml restart

# Stop all
docker compose -f docker-compose.prod.yml down

# Start all
docker compose -f docker-compose.prod.yml up -d
```

## Database Management

```bash
# Run migrations
docker exec ai-backend flask db upgrade

# Create new migration
docker exec ai-backend flask db migrate -m "description"

# Database shell
docker exec -it ai-mysql mysql -u ai_user -p ai_accounting

# Backup
docker exec ai-mysql mysqldump -u root -p ai_accounting | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore
gunzip < backup_20260528.sql.gz | docker exec -i ai-mysql mysql -u root -p ai_accounting
```

## Troubleshooting

### Service won't start
```bash
# Check container logs
docker logs ai-backend --tail=50

# Check health status
docker inspect ai-backend --format='{{.State.Health.Status}}'

# Check resource usage
docker stats --no-stream
```

### Database connection failed
```bash
# Check MySQL is healthy
docker inspect ai-mysql --format='{{.State.Health.Status}}'

# Test connection from backend container
docker exec ai-backend python -c "from app import create_app; app = create_app(); print('OK')"
```

### SSL issues
```bash
# Check certificate validity
openssl x509 -enddate -noout -in nginx/ssl/fullchain.pem

# Check nginx config
docker exec ai-nginx nginx -t

# Check nginx logs
docker logs ai-nginx --tail=50
```

### High memory usage
```bash
# Check container memory
docker stats --format "table {{.Name}}\t{{.MemUsage}}"

# Restart memory-heavy service
docker compose -f docker-compose.prod.yml restart elasticsearch
```

## Security Checklist

- [ ] SSH key-only authentication (no password)
- [ ] UFW firewall enabled
- [ ] fail2ban active
- [ ] All secrets rotated (no defaults)
- [ ] SSL certificate valid
- [ ] Monitoring ports not publicly exposed
- [ ] Docker daemon hardened
- [ ] Automatic security updates enabled
