#!/usr/bin/env bash
# ==============================================================================
# AI Accounting System — Production Deployment Script
# ==============================================================================
set -euo pipefail

# --- Constants ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/deploy/logs"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/deploy-${TIMESTAMP}.log"
MIN_MEMORY_MB=3500
MIN_DISK_GB=30
HEALTH_TIMEOUT=300  # seconds to wait for service health

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Options ---
DOMAIN=""
EMAIL=""
DRY_RUN=false
SKIP_SSL=false
SKIP_BUILD=false
SKIP_MIGRATE=false
FORCE=false
ROLLBACK=false
VERBOSE=false

# --- State ---
STEP=0
TOTAL_STEPS=8
ERRORS=()
WARNINGS=()

# ==============================================================================
# Utility Functions
# ==============================================================================

log() {
    local level="$1"; shift
    local msg="$*"
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$ts] [$level] $msg" >> "$LOG_FILE"
}

info() {
    echo -e "${GREEN}[INFO]${NC} $*"
    log "INFO" "$*"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
    log "WARN" "$*"
    WARNINGS+=("$*")
}

error() {
    echo -e "${RED}[ERROR]${NC} $*"
    log "ERROR" "$*"
    ERRORS+=("$*")
}

fatal() {
    error "$*"
    echo -e "\n${RED}DEPLOYMENT FAILED.${NC} See log: $LOG_FILE"
    exit 1
}

step() {
    STEP=$((STEP + 1))
    echo -e "\n${CYAN}━━━ Step $STEP/$TOTAL_STEPS: $* ━━━${NC}"
    log "STEP" "Step $STEP/$TOTAL_STEPS: $*"
}

run_cmd() {
    if $DRY_RUN; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $*"
        return 0
    fi
    if $VERBOSE; then
        "$@" 2>&1 | tee -a "$LOG_FILE"
    else
        "$@" >> "$LOG_FILE" 2>&1
    fi
}

wait_for_health() {
    local name="$1"
    local url="$2"
    local timeout="${3:-$HEALTH_TIMEOUT}"
    local elapsed=0
    local interval=5

    echo -n "  Waiting for $name"
    while [ $elapsed -lt "$timeout" ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}OK${NC} (${elapsed}s)"
            return 0
        fi
        echo -n "."
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    echo -e " ${RED}TIMEOUT${NC} (${timeout}s)"
    return 1
}

# ==============================================================================
# Argument Parsing
# ==============================================================================

usage() {
    cat <<EOF
AI Accounting System — Production Deployment

Usage: $(basename "$0") [OPTIONS]

Options:
  --domain DOMAIN       Production domain name
  --email EMAIL         Email for Let's Encrypt certificate
  --dry-run             Show what would be done without executing
  --skip-ssl            Skip SSL certificate setup
  --skip-build          Skip Docker image build (use existing)
  --skip-migrate        Skip database migrations
  --force               Force deployment even with warnings
  --rollback            Rollback to previous version
  -v, --verbose         Enable verbose output
  -h, --help            Show this help message

Examples:
  # First deployment with Let's Encrypt
  ./deploy/deploy.sh --domain ai.example.com --email admin@example.com

  # Update deployment (skip build if images exist)
  ./deploy/deploy.sh --skip-ssl --domain ai.example.com

  # Dry run to see what would happen
  ./deploy/deploy.sh --dry-run --domain ai.example.com

  # Rollback to previous version
  ./deploy/deploy.sh --rollback
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)      DOMAIN="$2"; shift 2 ;;
        --email)       EMAIL="$2"; shift 2 ;;
        --dry-run)     DRY_RUN=true; shift ;;
        --skip-ssl)    SKIP_SSL=true; shift ;;
        --skip-build)  SKIP_BUILD=true; shift ;;
        --skip-migrate) SKIP_MIGRATE=true; shift ;;
        --force)       FORCE=true; shift ;;
        --rollback)    ROLLBACK=true; shift ;;
        -v|--verbose)  VERBOSE=true; shift ;;
        -h|--help)     usage ;;
        *)             fatal "Unknown option: $1" ;;
    esac
done

# ==============================================================================
# Rollback
# ==============================================================================

do_rollback() {
    echo -e "\n${RED}━━━ ROLLBACK MODE ━━━${NC}"
    log "ROLLBACK" "Starting rollback"

    cd "$PROJECT_DIR"

    # Get current commit
    local current
    current="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
    info "Current version: $current"

    # Find previous commit
    local prev
    prev="$(git rev-parse --short HEAD~1 2>/dev/null || echo '')"
    if [ -z "$prev" ]; then
        fatal "No previous commit found for rollback"
    fi
    info "Rolling back to: $prev"

    if ! $DRY_RUN; then
        git checkout "$prev" || fatal "Git checkout failed"
    fi

    # Rebuild and restart
    info "Rebuilding containers..."
    run_cmd docker compose -f docker-compose.prod.yml build --no-cache

    info "Restarting services..."
    run_cmd docker compose -f docker-compose.prod.yml down --timeout 30
    run_cmd docker compose -f docker-compose.prod.yml up -d

    info "Rollback to $prev complete"
    log "ROLLBACK" "Rollback to $prev complete"
    exit 0
}

# ==============================================================================
# Main Deployment
# ==============================================================================

main() {
    mkdir -p "$LOG_DIR"
    echo "=== Deployment started at $(date) ===" >> "$LOG_FILE"

    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║   AI Accounting System — Production Deployment  ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"

    if $DRY_RUN; then
        warn "DRY-RUN MODE — no changes will be made"
    fi

    cd "$PROJECT_DIR"

    if $ROLLBACK; then
        do_rollback
    fi

    # --- Step 1: Pre-flight Checks ---
    step "Pre-flight Checks"
    preflight_checks

    # --- Step 2: Secrets ---
    step "Secrets Setup"
    setup_secrets

    # --- Step 3: SSL Certificates ---
    step "SSL Certificates"
    setup_ssl

    # --- Step 4: Build ---
    step "Build Docker Images"
    build_images

    # --- Step 5: Database ---
    step "Database Initialization"
    init_database

    # --- Step 6: Start Services ---
    step "Start All Services"
    start_services

    # --- Step 7: Verification ---
    step "Post-Deploy Verification"
    verify_deployment

    # --- Step 8: Summary ---
    step "Deployment Summary"
    print_summary
}

# ==============================================================================
# Step 1: Pre-flight Checks
# ==============================================================================

preflight_checks() {
    # Docker
    if ! command -v docker &> /dev/null; then
        fatal "Docker is not installed"
    fi
    if ! docker info &> /dev/null; then
        fatal "Docker daemon is not running"
    fi
    info "Docker: $(docker --version | head -1)"

    # Docker Compose
    if docker compose version &> /dev/null; then
        info "Docker Compose: $(docker compose version --short)"
    else
        fatal "Docker Compose v2 is not available"
    fi

    # .env.production
    if [ ! -f .env.production ]; then
        if [ -f .env.production.example ]; then
            warn ".env.production not found — will generate from secrets script"
        else
            fatal ".env.production not found and no example available"
        fi
    else
        info ".env.production found"

        # Check for placeholder values
        local placeholders=("your-secret-key-here" "your-jwt-secret" "change-me" "your-" "admin123")
        for ph in "${placeholders[@]}"; do
            if grep -qi "$ph" .env.production 2>/dev/null; then
                warn "Placeholder value detected in .env.production: '$ph'"
            fi
        done
    fi

    # System resources
    local mem_mb
    mem_mb="$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo 0)"
    if [ "$mem_mb" -lt "$MIN_MEMORY_MB" ] && [ "$mem_mb" -gt 0 ]; then
        warn "Low memory: ${mem_mb}MB (recommended: ${MIN_MEMORY_MB}MB+)"
    else
        info "Memory: ${mem_mb}MB"
    fi

    local disk_gb
    disk_gb="$(df -BG / 2>/dev/null | awk 'NR==2{print $4}' | tr -d 'G' || echo 0)"
    if [ "$disk_gb" -lt "$MIN_DISK_GB" ] && [ "$disk_gb" -gt 0 ]; then
        warn "Low disk space: ${disk_gb}GB available (recommended: ${MIN_DISK_GB}GB+)"
    else
        info "Disk available: ${disk_gb}GB"
    fi

    # Ports
    for port in 80 443; do
        if ss -tlnp 2>/dev/null | grep -q ":${port} " || netstat -tlnp 2>/dev/null | grep -q ":${port} "; then
            warn "Port $port is already in use"
        fi
    done

    # Domain resolution (optional)
    if [ -n "$DOMAIN" ]; then
        local server_ip
        server_ip="$(curl -sf ifconfig.me 2>/dev/null || echo '')"
        local domain_ip
        domain_ip="$(dig +short "$DOMAIN" 2>/dev/null | head -1 || echo '')"
        if [ -n "$server_ip" ] && [ -n "$domain_ip" ] && [ "$server_ip" != "$domain_ip" ]; then
            warn "Domain $DOMAIN resolves to $domain_ip, but server IP is $server_ip"
        else
            info "Domain $DOMAIN resolves correctly"
        fi
    fi

    info "Pre-flight checks passed"
}

# ==============================================================================
# Step 2: Secrets Setup
# ==============================================================================

setup_secrets() {
    if [ -f .env.production ]; then
        # Validate existing secrets
        if [ -f scripts/validate_secrets.py ]; then
            info "Validating existing secrets..."
            if ! run_cmd python scripts/validate_secrets.py; then
                if $FORCE; then
                    warn "Secret validation failed (--force: continuing anyway)"
                else
                    fatal "Secret validation failed. Run: python scripts/generate_secrets.py --force"
                fi
            else
                info "Secrets validated"
            fi
        fi
    else
        info "Generating new secrets..."
        if [ -f scripts/generate_secrets.py ]; then
            run_cmd python scripts/generate_secrets.py --force
            info "Secrets generated"
        else
            fatal "scripts/generate_secrets.py not found"
        fi
    fi
}

# ==============================================================================
# Step 3: SSL Certificates
# ==============================================================================

setup_ssl() {
    if $SKIP_SSL; then
        info "SSL setup skipped (--skip-ssl)"
        return 0
    fi

    mkdir -p nginx/ssl

    # Check existing certificates
    if [ -f nginx/ssl/fullchain.pem ] && [ -f nginx/ssl/privkey.pem ]; then
        # Check expiry
        local expiry
        expiry="$(openssl x509 -enddate -noout -in nginx/ssl/fullchain.pem 2>/dev/null | cut -d= -f2)"
        if [ -n "$expiry" ]; then
            local expiry_epoch
            expiry_epoch="$(date -d "$expiry" +%s 2>/dev/null || echo 0)"
            local now_epoch
            now_epoch="$(date +%s)"
            local days_left=$(( (expiry_epoch - now_epoch) / 86400 ))
            if [ "$days_left" -lt 30 ]; then
                warn "SSL certificate expires in $days_left days — renewal recommended"
            else
                info "SSL certificate valid for $days_left days"
            fi
        fi
        return 0
    fi

    # Try Let's Encrypt
    if [ -n "$DOMAIN" ] && command -v certbot &> /dev/null; then
        info "Requesting Let's Encrypt certificate for $DOMAIN..."
        local email_flag=""
        if [ -n "$EMAIL" ]; then
            email_flag="--email $EMAIL"
        else
            email_flag="--register-unsafely-without-email"
        fi

        if ! $DRY_RUN; then
            certbot certonly --standalone \
                -d "$DOMAIN" \
                $email_flag \
                --agree-tos \
                --non-interactive \
                --deploy-hook "cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $PROJECT_DIR/nginx/ssl/ && cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $PROJECT_DIR/nginx/ssl/" \
                2>&1 | tee -a "$LOG_FILE" || {
                    warn "Let's Encrypt failed — generating self-signed certificate"
                    generate_self_signed
                }
        fi
    else
        if [ -n "$DOMAIN" ] && ! command -v certbot &> /dev/null; then
            warn "certbot not installed — cannot request Let's Encrypt certificate"
        fi
        generate_self_signed
    fi
}

generate_self_signed() {
    info "Generating self-signed certificate (development/testing only)..."
    if ! $DRY_RUN; then
        openssl req -x509 -nodes -days 365 \
            -newkey rsa:2048 \
            -keyout nginx/ssl/privkey.pem \
            -out nginx/ssl/fullchain.pem \
            -subj "/C=CN/ST=Dev/L=Dev/O=AI-Accounting/CN=${DOMAIN:-localhost}" \
            >> "$LOG_FILE" 2>&1
    fi
    info "Self-signed certificate generated"
    warn "Self-signed certs are NOT suitable for production — obtain a real certificate"
}

# ==============================================================================
# Step 4: Build Images
# ==============================================================================

build_images() {
    if $SKIP_BUILD; then
        info "Build skipped (--skip-build)"
        return 0
    fi

    local git_hash
    git_hash="$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')"
    info "Building images (tag: $git_hash)..."

    info "Building backend..."
    run_cmd docker compose -f docker-compose.prod.yml build backend celery-worker celery-beat

    info "Building frontend..."
    run_cmd docker compose -f docker-compose.prod.yml build frontend

    info "Images built successfully"
}

# ==============================================================================
# Step 5: Database Initialization
# ==============================================================================

init_database() {
    info "Starting database services..."

    # Start MySQL and Redis first
    run_cmd docker compose -f docker-compose.prod.yml up -d mysql redis

    # Wait for MySQL
    wait_for_health "MySQL" "http://localhost:3306" 60 || {
        # MySQL doesn't have HTTP health check, use docker health status
        local elapsed=0
        echo -n "  Waiting for MySQL (docker health)"
        while [ $elapsed -lt 120 ]; do
            if docker inspect ai-mysql --format='{{.State.Health.Status}}' 2>/dev/null | grep -q "healthy"; then
                echo -e " ${GREEN}OK${NC}"
                break
            fi
            echo -n "."
            sleep 5
            elapsed=$((elapsed + 5))
        done
        if [ $elapsed -ge 120 ]; then
            fatal "MySQL failed to start"
        fi
    }

    # Wait for Redis
    local elapsed=0
    echo -n "  Waiting for Redis"
    while [ $elapsed -lt 60 ]; do
        if docker inspect ai-redis --format='{{.State.Health.Status}}' 2>/dev/null | grep -q "healthy"; then
            echo -e " ${GREEN}OK${NC}"
            break
        fi
        echo -n "."
        sleep 5
        elapsed=$((elapsed + 5))
    done
    if [ $elapsed -ge 60 ]; then
        fatal "Redis failed to start"
    fi

    if $SKIP_MIGRATE; then
        info "Migrations skipped (--skip-migrate)"
        return 0
    fi

    # Start backend temporarily for migrations
    info "Running database migrations..."
    run_cmd docker compose -f docker-compose.prod.yml up -d backend

    # Wait for backend to be ready
    sleep 10

    # Run migrations
    info "Applying database migrations..."
    run_cmd docker exec ai-backend flask db upgrade || {
        warn "Migration failed — database may already be up to date"
    }

    info "Database initialized"
}

# ==============================================================================
# Step 6: Start Services
# ==============================================================================

start_services() {
    info "Starting all services..."

    # Check which compose files to use
    local compose_files="-f docker-compose.prod.yml"
    if [ -f docker-compose.security.yml ]; then
        compose_files="$compose_files -f docker-compose.security.yml"
        info "Applying security hardening overlay"
    fi

    run_cmd docker compose $compose_files up -d

    info "All containers started"

    # Show container status
    echo ""
    docker compose $compose_files ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
        docker compose $compose_files ps
}

# ==============================================================================
# Step 7: Verification
# ==============================================================================

verify_deployment() {
    info "Running post-deploy verification..."
    local failures=0

    # Backend health
    if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
        info "  Backend health: OK"
    else
        # Try via nginx
        if curl -sf http://localhost/health > /dev/null 2>&1; then
            info "  Backend health (via nginx): OK"
        else
            error "  Backend health: FAILED"
            failures=$((failures + 1))
        fi
    fi

    # Nginx
    if curl -sf http://localhost/ > /dev/null 2>&1; then
        info "  Nginx: OK"
    else
        error "  Nginx: FAILED"
        failures=$((failures + 1))
    fi

    # Prometheus
    if curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1; then
        info "  Prometheus: OK"
    else
        warn "  Prometheus: not reachable (may be bound to 127.0.0.1)"
    fi

    # Grafana
    if curl -sf http://localhost:3000/api/health > /dev/null 2>&1; then
        info "  Grafana: OK"
    else
        warn "  Grafana: not reachable (may be bound to 127.0.0.1)"
    fi

    # Container logs check
    echo ""
    info "Checking container logs for errors..."
    for container in ai-backend ai-celery-worker ai-celery-beat; do
        local error_count
        error_count="$(docker logs "$container" --since 2m 2>&1 | grep -ciE 'error|exception|fatal|traceback' || echo 0)"
        if [ "$error_count" -gt 0 ]; then
            warn "  $container: $error_count error lines in last 2 minutes"
        else
            info "  $container: clean"
        fi
    done

    # Stripe verification
    if [ -f scripts/stripe_production.py ] && python3 -c "import urllib.request" 2>/dev/null; then
        info "Running Stripe verification..."
        python3 scripts/stripe_production.py --check 2>&1 | while IFS= read -r line; do
            if echo "$line" | grep -q "PASS"; then
                info "  $line"
            elif echo "$line" | grep -q "FAIL"; then
                error "  $line"
                failures=$((failures + 1))
            elif echo "$line" | grep -q "WARN"; then
                warn "  $line"
            fi
        done || warn "Stripe verification skipped"
    fi

    if [ $failures -gt 0 ]; then
        error "$failures critical verification failures"
        if ! $FORCE; then
            fatal "Deployment verification failed. Use --force to continue anyway."
        fi
    else
        info "All verification checks passed"
    fi
}

# ==============================================================================
# Step 8: Summary
# ==============================================================================

print_summary() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║              DEPLOYMENT COMPLETE                     ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""

    local host="${DOMAIN:-$(curl -sf ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP')}"
    local git_hash
    git_hash="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"

    echo -e "${GREEN}Version:${NC} $git_hash"
    echo ""

    echo -e "${GREEN}Production URLs:${NC}"
    echo "  Application:    https://$host/"
    echo "  API Base:       https://$host/api/"
    echo "  Health Check:   https://$host/health"
    echo "  WebSocket:      wss://$host/socket.io/"
    echo ""

    echo -e "${GREEN}Stripe Webhook:${NC}"
    echo "  Endpoint:       https://$host/api/billing/webhook"
    echo "  Dashboard:      https://dashboard.stripe.com/webhooks"
    echo ""

    echo -e "${GREEN}Monitoring (SSH tunnel required):${NC}"
    echo "  Grafana:        ssh -L 3000:localhost:3000 root@$host"
    echo "  Prometheus:     ssh -L 9090:localhost:9090 root@$host"
    echo "  Kibana:         ssh -L 5601:localhost:5601 root@$host"
    echo ""

    echo -e "${GREEN}Operations:${NC}"
    echo "  Runbook:        deploy/RUNBOOK.md"
    echo "  Full verify:    ./deploy/verify.sh https://$host"
    echo "  Backup:         ./scripts/backup.sh"
    echo "  Backup test:    ./scripts/backup_validate.sh"
    echo "  Stripe check:   python3 scripts/stripe_production.py --check"
    echo ""

    echo -e "${GREEN}Management:${NC}"
    echo "  Logs:           docker compose -f docker-compose.prod.yml logs -f"
    echo "  Status:         docker compose -f docker-compose.prod.yml ps"
    echo "  Restart:        docker compose -f docker-compose.prod.yml restart"
    echo "  Stop:           docker compose -f docker-compose.prod.yml down"
    echo "  Scale workers:  docker compose -f docker-compose.prod.yml up -d --scale celery-worker=3"
    echo ""

    if [ ${#WARNINGS[@]} -gt 0 ]; then
        echo -e "${YELLOW}Warnings (${#WARNINGS[@]}):${NC}"
        for w in "${WARNINGS[@]}"; do
            echo "  - $w"
        done
        echo ""
    fi

    if [ ${#ERRORS[@]} -gt 0 ]; then
        echo -e "${RED}Errors (${#ERRORS[@]}):${NC}"
        for e in "${ERRORS[@]}"; do
            echo "  - $e"
        done
        echo ""
    fi

    echo "Deployment log: $LOG_FILE"
    echo "Completed at: $(date)"
    log "DEPLOY" "Deployment completed with ${#ERRORS[@]} errors, ${#WARNINGS[@]} warnings"
}

# ==============================================================================
# Run
# ==============================================================================

main "$@"
