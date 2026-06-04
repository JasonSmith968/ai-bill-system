# Secrets Rotation Guide

This document covers how to generate, rotate, and validate production secrets
for the AI Accounting System.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Generating Initial Secrets](#generating-initial-secrets)
3. [Validating Secrets](#validating-secrets)
4. [Rotating Individual Secrets](#rotating-individual-secrets)
5. [Compromised Secret Response](#compromised-secret-response)
6. [Rotation Schedule](#rotation-schedule)
7. [Secrets Inventory](#secrets-inventory)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Generate all secrets
python scripts/generate_secrets.py

# 2. Review and customise
vi .env.production

# 3. Validate
python scripts/validate_secrets.py

# 4. Deploy
docker compose -f docker-compose.prod.yml up -d
```

---

## Generating Initial Secrets

### Full generation (new deployment)

```bash
python scripts/generate_secrets.py
```

This creates `.env.production` with all secrets filled in.  The script will
refuse to overwrite an existing file unless `--force` is passed.

```bash
python scripts/generate_secrets.py --force   # overwrite existing file
```

### What gets generated

| Secret | Length | Method |
|--------|--------|--------|
| `SECRET_KEY` | 64 hex chars | `secrets.token_hex(32)` |
| `JWT_SECRET_KEY` | 64 hex chars | `secrets.token_hex(32)` (guaranteed different from SECRET_KEY) |
| `FERNET_KEY` | 44 chars (base64) | `Fernet.generate_key()` |
| `MYSQL_ROOT_PASSWORD` | 32 alphanumeric | `secrets.choice()` |
| `MYSQL_PASSWORD` | 32 alphanumeric | `secrets.choice()` |
| `REDIS_PASSWORD` | 32 alphanumeric | `secrets.choice()` |
| `ADMIN_PASSWORD` | 24 mixed-case+digits | Guaranteed upper, lower, digit |
| `MYSQL_EXPORTER_PASSWORD` | 24 mixed-case+digits | Guaranteed upper, lower, digit |
| `GRAFANA_PASSWORD` | 24 mixed-case+digits | Guaranteed upper, lower, digit |
| `METRICS_AUTH_TOKEN` | 64 hex chars | `secrets.token_hex(32)` |
| `REQUEST_SIGNING_SECRET` | 64 hex chars | `secrets.token_hex(32)` |

### After generation

1. Open `.env.production` and review
2. Update `DATABASE_URL` host/port if not using default Docker networking
3. Set `DEEPSEEK_API_KEY` if using AI features
4. Update `CORS_ORIGINS` and `FRONTEND_URL` for your domain
5. Run `python scripts/validate_secrets.py` to confirm

---

## Validating Secrets

### Validate a file

```bash
# Default: validates .env.production in project root
python scripts/validate_secrets.py

# Specific file
python scripts/validate_secrets.py --env-file /path/to/.env.production

# Non-strict mode (allows non-production FLASK_ENV)
python scripts/validate_secrets.py --no-strict
```

### Validate environment variables directly

```bash
# When running inside Docker or CI where env vars are injected
python scripts/validate_secrets.py --from-env
```

### What gets checked

- All required variables are present and non-empty
- No placeholder/default values (e.g., `CHANGE_ME`, `password`, `123456`)
- `SECRET_KEY` and `JWT_SECRET_KEY` are different
- All secrets meet minimum length requirements
- `DATABASE_URL` does not contain default passwords
- `ADMIN_PASSWORD` is not a default value
- `FERNET_KEY` is valid base64 and decodes to 32 bytes

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | One or more checks failed |

---

## Rotating Individual Secrets

### Rotate a single secret

```bash
python scripts/generate_secrets.py --rotate SECRET_KEY
python scripts/generate_secrets.py --rotate JWT_SECRET_KEY
python scripts/generate_secrets.py --rotate MYSQL_PASSWORD
python scripts/generate_secrets.py --rotate REDIS_PASSWORD
```

The `--rotate` flag:

1. Reads the existing `.env.production`
2. Generates a new value for the specified variable only
3. Updates the variable in-place
4. For `MYSQL_PASSWORD` and `REDIS_PASSWORD`, also updates the derived
   `DATABASE_URL` / `REDIS_URL`
5. Leaves all other secrets untouched

### After rotating

#### Application secrets (SECRET_KEY, JWT_SECRET_KEY, FERNET_KEY)

```bash
# Restart the application
docker compose -f docker-compose.prod.yml restart backend

# Verify
curl https://your-domain.com/health
```

**Note:** Rotating `SECRET_KEY` invalidates all existing Flask sessions.
Rotating `JWT_SECRET_KEY` invalidates all existing JWT tokens.  Users will
need to log in again.

#### Database password (MYSQL_PASSWORD)

```bash
# 1. Update MySQL password
docker compose -f docker-compose.prod.yml exec db mysql -u root \
  -p"$(grep MYSQL_ROOT_PASSWORD .env.production | cut -d= -f2)" \
  -e "ALTER USER 'ai_user'@'%' IDENTIFIED BY 'NEW_PASSWORD';"

# 2. Restart application
docker compose -f docker-compose.prod.yml restart backend
```

#### Redis password (REDIS_PASSWORD)

```bash
# 1. Update Redis password
docker compose -f docker-compose.prod.yml exec redis redis-cli \
  -a "$(grep REDIS_PASSWORD .env.production | cut -d= -f2 --complement)" \
  CONFIG SET requirepass "NEW_PASSWORD"

# 2. Restart application and Celery workers
docker compose -f docker-compose.prod.yml restart backend celery-worker
```

#### Monitoring secrets (GRAFANA_PASSWORD, METRICS_AUTH_TOKEN, MYSQL_EXPORTER_PASSWORD)

```bash
# Update Grafana password via API or UI
# Update monitoring stack config
docker compose -f docker-compose.prod.yml restart grafana prometheus
```

---

## Compromised Secret Response

If a secret is suspected to be compromised, follow these steps immediately:

### Step 1: Rotate the compromised secret

```bash
python scripts/generate_secrets.py --rotate <COMPROMISED_VAR>
```

### Step 2: Deploy the new secret

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Step 3: Invalidate existing sessions/tokens

For `SECRET_KEY` or `JWT_SECRET_KEY` compromise:

```bash
# Force all users to re-authenticate
# (Rotating the keys does this automatically)
```

For `DATABASE_URL` compromise:

```bash
# Change MySQL password AND revoke any external access
# Audit database access logs
```

For `DEEPSEEK_API_KEY` compromise:

```bash
# Revoke the key at https://platform.deepseek.com
# Generate a new key
# Update .env.production
```

### Step 4: Audit and document

- Check access logs for unauthorised usage
- Document the incident in your incident response system
- Review how the secret was compromised
- Consider shortening the rotation interval for the affected secret

---

## Rotation Schedule

| Secret | Recommended Interval | Notes |
|--------|---------------------|-------|
| `SECRET_KEY` | Every 90 days | Invalidates all sessions |
| `JWT_SECRET_KEY` | Every 90 days | Invalidates all tokens |
| `FERNET_KEY` | Every 180 days | Requires re-encryption of stored data |
| `MYSQL_ROOT_PASSWORD` | Every 90 days | Coordinate with DBA |
| `MYSQL_PASSWORD` | Every 90 days | Use `--rotate` for safe update |
| `REDIS_PASSWORD` | Every 90 days | Use `--rotate` for safe update |
| `ADMIN_PASSWORD` | Every 60 days | Change via admin panel |
| `MYSQL_EXPORTER_PASSWORD` | Every 180 days | |
| `GRAFANA_PASSWORD` | Every 90 days | |
| `METRICS_AUTH_TOKEN` | Every 180 days | |
| `REQUEST_SIGNING_SECRET` | Every 180 days | |
| `DEEPSEEK_API_KEY` | Every 90 days | Rotate at provider portal |

### Automating rotation

```bash
# Cron job: rotate all secrets quarterly (add to crontab)
# 0 3 1 */3 * cd /opt/ai-accounting-system && python scripts/generate_secrets.py --force && docker compose -f docker-compose.prod.yml up -d
```

**Warning:** Rotating `SECRET_KEY` and `JWT_SECRET_KEY` forces all users to
log in again.  Schedule these rotations during low-traffic periods.

---

## Secrets Inventory

| Variable | Purpose | Min Length | Format |
|----------|---------|------------|--------|
| `SECRET_KEY` | Flask session signing | 64 | Hex string |
| `JWT_SECRET_KEY` | JWT token signing | 64 | Hex string |
| `FERNET_KEY` | Symmetric encryption | 44 | Base64 (32 bytes) |
| `MYSQL_ROOT_PASSWORD` | MySQL root access | 32 | Alphanumeric |
| `MYSQL_PASSWORD` | MySQL app access | 32 | Alphanumeric |
| `REDIS_PASSWORD` | Redis access | 32 | Alphanumeric |
| `ADMIN_PASSWORD` | Initial admin user | 24 | Mixed-case + digits |
| `MYSQL_EXPORTER_PASSWORD` | Prometheus exporter | 24 | Mixed-case + digits |
| `GRAFANA_PASSWORD` | Grafana admin | 24 | Mixed-case + digits |
| `METRICS_AUTH_TOKEN` | /metrics endpoint auth | 64 | Hex string |
| `REQUEST_SIGNING_SECRET` | Request HMAC signing | 64 | Hex string |

---

## Troubleshooting

### "SECRET_KEY appears to be a placeholder value"

The startup validator detected a known placeholder.  Generate a real key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### "SECRET_KEY and JWT_SECRET_KEY must be different"

These two keys must never be the same.  Generate distinct values:

```bash
python scripts/generate_secrets.py --rotate SECRET_KEY
python scripts/generate_secrets.py --rotate JWT_SECRET_KEY
```

### "DATABASE_URL contains weak password component"

The password embedded in `DATABASE_URL` matches a known weak password.
Update the password portion of the URL:

```
DATABASE_URL=mysql+pymysql://ai_user:STRONG_PASSWORD_HERE@db:3306/ai_accounting
```

### "FERNET_KEY is not valid base64"

Regenerate the Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Startup validator blocks application start

In production (`FLASK_ENV=production`), the application will refuse to start
if secrets are misconfigured.  Fix the issues reported, then restart.

In development, only warnings are logged -- the application will start
regardless.
