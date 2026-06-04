#!/usr/bin/env bash
# ==============================================================================
# AI Accounting System — Backup & Restore Validation
# ==============================================================================
# Creates backup, verifies integrity, tests restore to temp database
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

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

MYSQL_USER="${MYSQL_USER:-ai_user}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"
MYSQL_DATABASE="${MYSQL_DATABASE:-ai_accounting}"
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-}"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Backup & Restore Validation                       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

PASS=0
FAIL=0

check() {
    local name="$1"
    local result="$2"
    if [ "$result" = "ok" ]; then
        echo -e "  ${GREEN}PASS${NC} $name"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC} $name: $result"
        FAIL=$((FAIL + 1))
    fi
}

# ==============================================================================
# 1. Create Backup
# ==============================================================================

echo -e "${CYAN}━━━ 1. Create Backup ━━━${NC}"

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/backup_test_${TIMESTAMP}.sql.gz"

info "Creating backup..."
docker exec ai-mysql mysqldump \
    -u root \
    -p"${MYSQL_ROOT_PASSWORD}" \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --add-drop-database \
    --databases "${MYSQL_DATABASE}" 2>/dev/null | gzip > "$BACKUP_FILE"

if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
    FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    check "Backup created ($FILESIZE)" "ok"
else
    check "Backup created" "failed to create backup file"
    exit 1
fi

# ==============================================================================
# 2. Verify Backup Integrity
# ==============================================================================

echo -e "\n${CYAN}━━━ 2. Verify Backup Integrity ━━━${NC}"

# Check gzip integrity
if gzip -t "$BACKUP_FILE" 2>/dev/null; then
    check "Gzip integrity" "ok"
else
    check "Gzip integrity" "corrupt gzip file"
fi

# Check SQL content
SQL_CONTENT=$(zcat "$BACKUP_FILE" 2>/dev/null | head -50)
if echo "$SQL_CONTENT" | grep -q "MySQL dump"; then
    check "SQL header present" "ok"
else
    check "SQL header present" "missing MySQL dump header"
fi

if echo "$SQL_CONTENT" | grep -q "CREATE TABLE\|CREATE DATABASE"; then
    check "Schema statements present" "ok"
else
    check "Schema statements present" "no CREATE statements found"
fi

# Check table count
TABLE_COUNT=$(zcat "$BACKUP_FILE" 2>/dev/null | grep -c "CREATE TABLE" || echo 0)
info "Tables in backup: $TABLE_COUNT"
if [ "$TABLE_COUNT" -gt 0 ]; then
    check "Tables found ($TABLE_COUNT)" "ok"
else
    check "Tables found" "no tables in backup"
fi

# ==============================================================================
# 3. Test Restore to Temporary Database
# ==============================================================================

echo -e "\n${CYAN}━━━ 3. Test Restore ━━━${NC}"

TEST_DB="ai_accounting_restore_test_$(date +%s)"

info "Creating temporary database: $TEST_DB"
docker exec ai-mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "CREATE DATABASE IF NOT EXISTS \`$TEST_DB\`;" 2>/dev/null

if docker exec -i ai-mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" "$TEST_DB" < <(zcat "$BACKUP_FILE") 2>/dev/null; then
    check "Restore to temp DB" "ok"
else
    check "Restore to temp DB" "restore failed"
fi

# Verify restored tables
RESTORED_TABLES=$(docker exec ai-mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -N -e \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$TEST_DB';" 2>/dev/null || echo 0)

if [ "$RESTORED_TABLES" -gt 0 ]; then
    check "Restored tables ($RESTORED_TABLES)" "ok"
else
    check "Restored tables" "no tables after restore"
fi

# Verify row counts match
info "Comparing row counts..."
TABLES=$(docker exec ai-mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -N -e \
    "SELECT table_name FROM information_schema.tables WHERE table_schema='${MYSQL_DATABASE}' AND table_type='BASE TABLE';" 2>/dev/null)

MISMATCH=0
for table in $TABLES; do
    ORIG_COUNT=$(docker exec ai-mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -N -e \
        "SELECT COUNT(*) FROM \`${MYSQL_DATABASE}\`.\`${table}\`;" 2>/dev/null || echo -1)
    RESTORE_COUNT=$(docker exec ai-mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -N -e \
        "SELECT COUNT(*) FROM \`${TEST_DB}\`.\`${table}\`;" 2>/dev/null || echo -1)

    if [ "$ORIG_COUNT" != "$RESTORE_COUNT" ]; then
        warn "  $table: original=$ORIG_COUNT restored=$RESTORE_COUNT"
        MISMATCH=$((MISMATCH + 1))
    fi
done

if [ $MISMATCH -eq 0 ]; then
    check "Row counts match" "ok"
else
    check "Row counts match" "$MISMATCH table(s) have mismatched counts"
fi

# ==============================================================================
# 4. Cleanup
# ==============================================================================

echo -e "\n${CYAN}━━━ 4. Cleanup ━━━${NC}"

info "Dropping temporary database: $TEST_DB"
docker exec ai-mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "DROP DATABASE IF EXISTS \`$TEST_DB\`;" 2>/dev/null

# Keep the test backup for reference
info "Test backup retained: $BACKUP_FILE"

# Clean backups older than 7 days
OLD_COUNT=$(find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 | wc -l)
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete 2>/dev/null || true
info "Cleaned $OLD_COUNT old backup(s)"

# ==============================================================================
# Summary
# ==============================================================================

TOTAL=$((PASS + FAIL))
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC} ($TOTAL total)"
echo ""

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}BACKUP VALIDATION FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}BACKUP VALIDATION PASSED${NC}"
    exit 0
fi
