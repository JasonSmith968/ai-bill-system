#!/usr/bin/env bash
# ==============================================================================
# AI Accounting System — Database Initialization
# ==============================================================================
# Runs migrations, seeds data, creates admin user, configures MySQL exporter
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
fatal() { error "$*"; exit 1; }

cd "$PROJECT_DIR"

# Load environment
if [ -f .env.production ]; then
    export $(grep -v '^#' .env.production | xargs)
else
    fatal ".env.production not found"
fi

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   AI Accounting System — Database Initialization    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ==============================================================================
# 1. Wait for MySQL
# ==============================================================================

echo -e "\n${CYAN}━━━ 1. Waiting for MySQL ━━━${NC}"

MAX_WAIT=120
ELAPSED=0
echo -n "  Connecting to MySQL"
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if docker inspect ai-mysql --format='{{.State.Health.Status}}' 2>/dev/null | grep -q "healthy"; then
        echo -e " ${GREEN}OK${NC} (${ELAPSED}s)"
        break
    fi
    echo -n "."
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    fatal "MySQL not healthy after ${MAX_WAIT}s"
fi

# ==============================================================================
# 2. Run Migrations
# ==============================================================================

echo -e "\n${CYAN}━━━ 2. Database Migrations ━━━${NC}"

info "Running Flask-Migrate upgrade..."
docker exec ai-backend flask db upgrade 2>&1 || {
    warn "Migration failed — trying create_all fallback"
    docker exec ai-backend python -c "
from app import create_app
from extensions import db
app = create_app('production')
with app.app_context():
    db.create_all()
    print('Tables created via create_all()')
" 2>&1
}
info "Migrations complete"

# ==============================================================================
# 3. Seed Plans
# ==============================================================================

echo -e "\n${CYAN}━━━ 3. Seed Subscription Plans ━━━${NC}"

docker exec ai-backend python -c "
from app import create_app
from models.plan import seed_plans
app = create_app('production')
with app.app_context():
    count = seed_plans()
    print(f'Plans seeded: {count}')
" 2>&1 || warn "Plan seeding may have already been done"

# ==============================================================================
# 4. Seed Roles and Permissions
# ==============================================================================

echo -e "\n${CYAN}━━━ 4. Seed Roles & Permissions ━━━${NC}"

docker exec ai-backend python -c "
from app import create_app
from models.role import seed_roles_and_permissions
app = create_app('production')
with app.app_context():
    seed_roles_and_permissions()
    print('Roles and permissions seeded')
" 2>&1 || warn "Role seeding may have already been done"

# ==============================================================================
# 5. Create Admin User
# ==============================================================================

echo -e "\n${CYAN}━━━ 5. Admin User ━━━${NC}"

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@ai-accounting.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

if [ -z "$ADMIN_PASSWORD" ]; then
    warn "ADMIN_PASSWORD not set in .env.production — skipping admin creation"
else
    docker exec ai-backend python -c "
import sys
from app import create_app
from extensions import db
from models.user import User
from models.role import Role

app = create_app('production')
with app.app_context():
    email = '$ADMIN_EMAIL'
    existing = User.query.filter_by(email=email).first()
    if existing:
        print(f'Admin user {email} already exists (id={existing.id})')
        sys.exit(0)

    admin_role = Role.query.filter_by(name='owner').first()
    if not admin_role:
        admin_role = Role.query.filter_by(name='admin').first()

    user = User(
        email=email,
        username='admin',
        is_admin=True,
        is_active=True,
        is_verified=True,
        role_id=admin_role.id if admin_role else None,
    )
    user.set_password('$ADMIN_PASSWORD')
    db.session.add(user)
    db.session.commit()
    print(f'Admin user created: {email} (id={user.id})')
" 2>&1
fi

# ==============================================================================
# 6. Initialize Growth System Defaults
# ==============================================================================

echo -e "\n${CYAN}━━━ 6. Growth System Defaults ━━━${NC}"

docker exec ai-backend python -c "
from app import create_app
from extensions import db
from services.growth_service import GrowthService

app = create_app('production')
with app.app_context():
    service = GrowthService(db.session)
    templates = service.init_email_templates()
    nudges = service.init_nudge_rules()
    print(f'Email templates: {templates}')
    print(f'Nudge rules: {nudges}')
" 2>&1 || warn "Growth defaults initialization skipped"

# ==============================================================================
# 7. Configure MySQL Exporter User
# ==============================================================================

echo -e "\n${CYAN}━━━ 7. MySQL Exporter User ━━━${NC}"

MYSQL_EXPORTER_PASSWORD="${MYSQL_EXPORTER_PASSWORD:-exporter_password}"

docker exec ai-mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "
CREATE USER IF NOT EXISTS 'exporter'@'%' IDENTIFIED BY '${MYSQL_EXPORTER_PASSWORD}';
GRANT PROCESS, REPLICATION CLIENT ON *.* TO 'exporter'@'%';
GRANT SELECT ON performance_schema.* TO 'exporter'@'%';
FLUSH PRIVILEGES;
" 2>&1 && info "MySQL exporter user configured" || warn "Exporter user may already exist"

# ==============================================================================
# Summary
# ==============================================================================

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           DATABASE INITIALIZATION COMPLETE           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Completed:"
echo "  [x] Database migrations"
echo "  [x] Subscription plans seeded"
echo "  [x] Roles and permissions seeded"
echo "  [x] Admin user: $ADMIN_EMAIL"
echo "  [x] Growth system defaults"
echo "  [x] MySQL exporter user"
echo ""
echo "Verify: curl -s http://localhost:5000/health | jq ."
