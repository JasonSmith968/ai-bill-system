#!/usr/bin/env bash
# ==============================================================================
# AI Accounting System — Server Initialization (Ubuntu 24.04 LTS)
# ==============================================================================
# Installs: Docker, Docker Compose, certbot, monitoring prerequisites
# Then runs: harden.sh for security hardening
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="/var/log/server-init.log"

DOMAIN="${DOMAIN:-}"
EMAIL="${EMAIL:-}"
SSH_PORT="${SSH_PORT:-22}"
ADMIN_IP="${ADMIN_IP:-}"
SKIP_HARDEN="${SKIP_HARDEN:-false}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }
info() { echo -e "${GREEN}[INFO]${NC} $*"; log "INFO: $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; log "WARN: $*"; }
fatal() { echo -e "${RED}[FATAL]${NC} $*"; log "FATAL: $*"; exit 1; }

# ==============================================================================
# Parse Arguments
# ==============================================================================

usage() {
    cat <<EOF
AI Accounting System — Server Initialization

Usage: sudo $(basename "$0") [OPTIONS]

Options:
  --domain DOMAIN       Production domain (e.g., ai.example.com)
  --email EMAIL         Email for Let's Encrypt
  --ssh-port PORT       Custom SSH port (default: 22)
  --admin-ip IP         Admin IP for monitoring access
  --skip-harden         Skip security hardening step
  -h, --help            Show this help

Example:
  sudo ./deploy/init_server.sh --domain ai.example.com --email admin@example.com
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)       DOMAIN="$2"; shift 2 ;;
        --email)        EMAIL="$2"; shift 2 ;;
        --ssh-port)     SSH_PORT="$2"; shift 2 ;;
        --admin-ip)     ADMIN_IP="$2"; shift 2 ;;
        --skip-harden)  SKIP_HARDEN=true; shift ;;
        -h|--help)      usage ;;
        *)              fatal "Unknown option: $1" ;;
    esac
done

# ==============================================================================
# Check Root
# ==============================================================================

if [ "$(id -u)" -ne 0 ]; then
    fatal "This script must be run as root: sudo $0 $*"
fi

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   AI Accounting System — Server Initialization      ║"
echo "║   Ubuntu 24.04 LTS                                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ==============================================================================
# 1. System Update
# ==============================================================================

echo -e "\n${CYAN}━━━ 1. System Update ━━━${NC}"
info "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    curl wget git vim htop tree jq \
    ca-certificates gnupg lsb-release \
    software-properties-common apt-transport-https
info "System updated"

# ==============================================================================
# 2. Install Docker
# ==============================================================================

echo -e "\n${CYAN}━━━ 2. Install Docker ━━━${NC}"

if command -v docker &> /dev/null; then
    info "Docker already installed: $(docker --version)"
else
    info "Installing Docker..."
    # Add Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Start and enable
    systemctl enable docker
    systemctl start docker

    info "Docker installed: $(docker --version)"
fi

# Verify Docker Compose
if docker compose version &> /dev/null; then
    info "Docker Compose: $(docker compose version --short)"
else
    fatal "Docker Compose v2 not available"
fi

# ==============================================================================
# 3. Install certbot (Let's Encrypt)
# ==============================================================================

echo -e "\n${CYAN}━━━ 3. Install certbot ━━━${NC}"

if command -v certbot &> /dev/null; then
    info "certbot already installed: $(certbot --version 2>&1 | head -1)"
else
    info "Installing certbot..."
    apt-get install -y -qq certbot
    info "certbot installed: $(certbot --version 2>&1 | head -1)"
fi

# ==============================================================================
# 4. Install monitoring prerequisites
# ==============================================================================

echo -e "\n${CYAN}━━━ 4. Monitoring Prerequisites ━━━${NC}"

# Ensure required directories exist
mkdir -p /var/log/nginx
mkdir -p /var/www/certbot

# Install logrotate config for nginx
cat > /etc/logrotate.d/nginx-docker <<'EOF'
/var/log/nginx/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        docker exec ai-nginx nginx -s reopen 2>/dev/null || true
    endscript
}
EOF
info "Logrotate configured"

# ==============================================================================
# 5. Setup project directory
# ==============================================================================

echo -e "\n${CYAN}━━━ 5. Project Directory ━━━${NC}"

# Create required directories
mkdir -p "$PROJECT_DIR"/{deploy/logs,nginx/ssl,backups,monitoring/grafana/provisioning,monitoring/grafana/dashboards,elk}

info "Project directories created"

# ==============================================================================
# 6. Generate SSL certificates
# ==============================================================================

echo -e "\n${CYAN}━━━ 6. SSL Certificates ━━━${NC}"

if [ -n "$DOMAIN" ]; then
    # Stop nginx if running (port 80 needed for standalone mode)
    docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" stop nginx 2>/dev/null || true

    EMAIL_FLAG=""
    if [ -n "$EMAIL" ]; then
        EMAIL_FLAG="--email $EMAIL"
    else
        EMAIL_FLAG="--register-unsafely-without-email"
    fi

    info "Requesting Let's Encrypt certificate for $DOMAIN..."
    certbot certonly --standalone \
        -d "$DOMAIN" \
        $EMAIL_FLAG \
        --agree-tos \
        --non-interactive \
        --cert-path /etc/letsencrypt/live/$DOMAIN/cert.pem \
        --key-path /etc/letsencrypt/live/$DOMAIN/privkey.pem \
        --fullchain-path /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
        2>&1 | tee -a "$LOG_FILE" || {
            warn "Let's Encrypt failed — generating self-signed certificate"
            openssl req -x509 -nodes -days 365 \
                -newkey rsa:2048 \
                -keyout "$PROJECT_DIR/nginx/ssl/privkey.pem" \
                -out "$PROJECT_DIR/nginx/ssl/fullchain.pem" \
                -subj "/C=CN/ST=Prod/L=Prod/O=AI-Accounting/CN=$DOMAIN" \
                2>/dev/null
        }

    # Copy certificates to nginx directory
    if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem "$PROJECT_DIR/nginx/ssl/"
        cp /etc/letsencrypt/live/$DOMAIN/privkey.pem "$PROJECT_DIR/nginx/ssl/"
        info "Let's Encrypt certificate installed"
    fi

    # Setup auto-renewal cron
    cat > /etc/cron.d/certbot-renewal <<CRONEOF
0 3 * * * root certbot renew --quiet --deploy-hook "cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $PROJECT_DIR/nginx/ssl/ && cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $PROJECT_DIR/nginx/ssl/ && docker exec ai-nginx nginx -s reload" >> /var/log/certbot-renewal.log 2>&1
CRONEOF
    info "Certbot auto-renewal cron installed"
else
    warn "No domain specified — generating self-signed certificate"
    openssl req -x509 -nodes -days 365 \
        -newkey rsa:2048 \
        -keyout "$PROJECT_DIR/nginx/ssl/privkey.pem" \
        -out "$PROJECT_DIR/nginx/ssl/fullchain.pem" \
        -subj "/C=CN/ST=Dev/L=Dev/O=AI-Accounting/CN=localhost" \
        2>/dev/null
    info "Self-signed certificate generated"
fi

# ==============================================================================
# 7. Security Hardening
# ==============================================================================

if [ "$SKIP_HARDEN" = "false" ]; then
    echo -e "\n${CYAN}━━━ 7. Security Hardening ━━━${NC}"
    info "Running hardening script..."

    HARDEN_ARGS=""
    [ -n "$SSH_PORT" ] && HARDEN_ARGS="$HARDEN_ARGS --ssh-port $SSH_PORT"
    [ -n "$ADMIN_IP" ] && HARDEN_ARGS="$HARDEN_ARGS --admin-ip $ADMIN_IP"

    bash "$SCRIPT_DIR/harden.sh" $HARDEN_ARGS
else
    echo -e "\n${CYAN}━━━ 7. Security Hardening (SKIPPED) ━━━${NC}"
    warn "Security hardening skipped"
fi

# ==============================================================================
# 8. Docker configuration for project
# ==============================================================================

echo -e "\n${CYAN}━━━ 8. Docker Configuration ━━━${NC}"

# Create .env.production if it doesn't exist
if [ ! -f "$PROJECT_DIR/.env.production" ]; then
    if [ -f "$PROJECT_DIR/scripts/generate_secrets.py" ]; then
        info "Generating production secrets..."
        cd "$PROJECT_DIR"
        python3 scripts/generate_secrets.py --force
        info "Secrets generated"
    else
        warn "No generate_secrets.py found — create .env.production manually"
    fi
else
    info ".env.production already exists"
fi

# Update domain in .env.production if specified
if [ -n "$DOMAIN" ] && [ -f "$PROJECT_DIR/.env.production" ]; then
    sed -i "s|CORS_ORIGINS=.*|CORS_ORIGINS=https://$DOMAIN|" "$PROJECT_DIR/.env.production"
    sed -i "s|FRONTEND_URL=.*|FRONTEND_URL=https://$DOMAIN|" "$PROJECT_DIR/.env.production"
    info "Updated CORS_ORIGINS and FRONTEND_URL to https://$DOMAIN"
fi

# ==============================================================================
# Summary
# ==============================================================================

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           SERVER INITIALIZATION COMPLETE             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Installed:"
echo "  [x] Docker $(docker --version 2>/dev/null | awk '{print $3}' || echo 'N/A')"
echo "  [x] Docker Compose $(docker compose version --short 2>/dev/null || echo 'N/A')"
echo "  [x] certbot $(certbot --version 2>&1 | awk '{print $2}' || echo 'N/A')"
echo "  [x] SSL certificates"
echo "  [x] Auto-renewal cron"
echo "  [x] Logrotate"
echo ""
echo "Next steps:"
echo "  1. Review .env.production: cat $PROJECT_DIR/.env.production"
echo "  2. Set DEEPSEEK_API_KEY if using AI features"
echo "  3. Deploy: cd $PROJECT_DIR && ./deploy/deploy.sh --domain $DOMAIN --skip-ssl"
echo ""
echo "Log: $LOG_FILE"
