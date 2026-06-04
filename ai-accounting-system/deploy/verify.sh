#!/usr/bin/env bash
# ==============================================================================
# AI Accounting System — Post-Deploy Verification Script
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

BASE_URL="${1:-http://localhost}"
PASS=0
FAIL=0
WARN=0
RESULTS=()

check() {
    local name="$1"
    local url="$2"
    local expected="${3:-200}"

    local status
    status="$(curl -sf -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 10 "$url" 2>/dev/null || echo '000')"

    if [ "$status" = "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC} $name (HTTP $status)"
        PASS=$((PASS + 1))
        RESULTS+=("PASS|$name|HTTP $status")
    else
        echo -e "  ${RED}FAIL${NC} $name (HTTP $status, expected $expected)"
        FAIL=$((FAIL + 1))
        RESULTS+=("FAIL|$name|HTTP $status (expected $expected)")
    fi
}

check_docker() {
    local name="$1"
    local container="$2"

    local status
    status="$(docker inspect "$container" --format='{{.State.Status}}' 2>/dev/null || echo 'missing')"

    if [ "$status" = "running" ]; then
        local health
        health="$(docker inspect "$container" --format='{{.State.Health.Status}}' 2>/dev/null || echo 'none')"
        if [ "$health" = "healthy" ] || [ "$health" = "none" ]; then
            echo -e "  ${GREEN}PASS${NC} $name (running, health=$health)"
            PASS=$((PASS + 1))
            RESULTS+=("PASS|$name|running health=$health")
        else
            echo -e "  ${YELLOW}WARN${NC} $name (running, health=$health)"
            WARN=$((WARN + 1))
            RESULTS+=("WARN|$name|running health=$health")
        fi
    else
        echo -e "  ${RED}FAIL${NC} $name (status=$status)"
        FAIL=$((FAIL + 1))
        RESULTS+=("FAIL|$name|status=$status")
    fi
}

check_container_logs() {
    local name="$1"
    local container="$2"
    local since="${3:-5m}"

    local error_count
    error_count="$(docker logs "$container" --since "$since" 2>&1 | grep -ciE 'error|exception|fatal|traceback|critical' || echo 0)"

    if [ "$error_count" -eq 0 ]; then
        echo -e "  ${GREEN}PASS${NC} $name logs clean"
        PASS=$((PASS + 1))
        RESULTS+=("PASS|$name|no errors in ${since}")
    else
        echo -e "  ${YELLOW}WARN${NC} $name has $error_count error lines in last $since"
        WARN=$((WARN + 1))
        RESULTS+=("WARN|$name|$error_count errors in ${since}")
    fi
}

# ==============================================================================
# Main
# ==============================================================================

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║   AI Accounting System — Verification Suite     ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "Target: $BASE_URL"
echo "Time:   $(date)"
echo ""

# --- Container Health ---
echo -e "${CYAN}━━━ Container Health ━━━${NC}"
check_docker "MySQL"         "ai-mysql"
check_docker "Redis"         "ai-redis"
check_docker "Backend"       "ai-backend"
check_docker "Celery Worker" "ai-celery-worker"
check_docker "Celery Beat"   "ai-celery-beat"
check_docker "Frontend"      "ai-frontend"
check_docker "Nginx"         "ai-nginx"
check_docker "Prometheus"    "ai-prometheus"
check_docker "Grafana"       "ai-grafana"
check_docker "ES"            "ai-elasticsearch"
check_docker "Kibana"        "ai-kibana"
echo ""

# --- HTTP Endpoints ---
echo -e "${CYAN}━━━ HTTP Endpoints ━━━${NC}"
check "Health"           "$BASE_URL/health"
check "Frontend"         "$BASE_URL/"
check "API Auth"         "$BASE_URL/api/auth/login" "405"
check "API Transactions" "$BASE_URL/api/transactions" "401"
check "API Dashboard"    "$BASE_URL/api/dashboard/summary" "401"
check "Blocked .env"     "$BASE_URL/.env" "404"
check "Blocked git"      "$BASE_URL/.git/config" "404"
echo ""

# --- WebSocket ---
echo -e "${CYAN}━━━ WebSocket ━━━${NC}"
WS_URL="${BASE_URL/https/wss}"
WS_URL="${WS_URL/http/ws}"
if command -v wscat &> /dev/null; then
    WS_STATUS="$(timeout 5 wscat -c "$WS_URL/socket.io/?EIO=4&transport=websocket" 2>&1 | head -1 || echo 'timeout')"
    if echo "$WS_STATUS" | grep -qi "connected\|open\|0{" ; then
        echo -e "  ${GREEN}PASS${NC} WebSocket connection"
        PASS=$((PASS + 1))
        RESULTS+=("PASS|WebSocket|connected")
    else
        echo -e "  ${YELLOW}WARN${NC} WebSocket: $WS_STATUS"
        WARN=$((WARN + 1))
        RESULTS+=("WARN|WebSocket|$WS_STATUS")
    fi
else
    # Fallback: check via HTTP upgrade
    WS_STATUS="$(curl -sf -o /dev/null -w '%{http_code}' \
        -H "Upgrade: websocket" -H "Connection: Upgrade" \
        "$BASE_URL/socket.io/?EIO=4&transport=polling" 2>/dev/null || echo '000')"
    if [ "$WS_STATUS" = "200" ]; then
        echo -e "  ${GREEN}PASS${NC} Socket.IO polling endpoint"
        PASS=$((PASS + 1))
        RESULTS+=("PASS|Socket.IO polling|HTTP 200")
    else
        echo -e "  ${YELLOW}WARN${NC} Socket.IO polling: HTTP $WS_STATUS"
        WARN=$((WARN + 1))
        RESULTS+=("WARN|Socket.IO polling|HTTP $WS_STATUS")
    fi
fi
echo ""

# --- Monitoring ---
echo -e "${CYAN}━━━ Monitoring ━━━${NC}"
check "Prometheus Health" "http://localhost:9090/-/healthy" "200"
check "Prometheus Targets" "http://localhost:9090/api/v1/targets" "200"
check "Grafana Health" "http://localhost:3000/api/health" "200"

# Prometheus targets
TARGETS_UP="$(curl -sf http://localhost:9090/api/v1/targets 2>/dev/null | python3 -c "
import json,sys
data=json.load(sys.stdin)
up=sum(1 for t in data.get('data',{}).get('activeTargets',[]) if t.get('health')=='up')
total=len(data.get('data',{}).get('activeTargets',[]))
print(f'{up}/{total}')
" 2>/dev/null || echo 'N/A')"
echo -e "  Prometheus targets: $TARGETS_UP up"
echo ""

# --- ELK Stack ---
echo -e "${CYAN}━━━ ELK Stack ━━━${NC}"
check "Elasticsearch" "http://localhost:9200/_cluster/health" "200"
check "Kibana Status" "http://localhost:5601/api/status" "200"

ES_STATUS="$(curl -sf http://localhost:9200/_cluster/health 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d.get('status','unknown'))
" 2>/dev/null || echo 'unknown')"
echo -e "  Elasticsearch cluster: $ES_STATUS"
echo ""

# --- Container Logs ---
echo -e "${CYAN}━━━ Container Logs (last 5m) ━━━${NC}"
check_container_logs "Backend"       "ai-backend" "5m"
check_container_logs "Celery Worker" "ai-celery-worker" "5m"
check_container_logs "Nginx"         "ai-nginx" "5m"
echo ""

# --- Security Checks ---
echo -e "${CYAN}━━━ Security ━━━${NC}"

# HTTPS redirect
HTTP_STATUS="$(curl -sf -o /dev/null -w '%{http_code}' "http://$(echo "$BASE_URL" | sed 's|https\?://||' | cut -d/ -f1)/" 2>/dev/null || echo '000')"
if [ "$HTTP_STATUS" = "301" ] || [ "$HTTP_STATUS" = "302" ]; then
    echo -e "  ${GREEN}PASS${NC} HTTP -> HTTPS redirect"
    PASS=$((PASS + 1))
else
    echo -e "  ${YELLOW}WARN${NC} HTTP redirect: $HTTP_STATUS"
    WARN=$((WARN + 1))
fi

# Security headers
HEADERS="$(curl -sf -I "$BASE_URL/" 2>/dev/null || echo '')"
for header in "X-Frame-Options" "X-Content-Type-Options" "Strict-Transport-Security"; do
    if echo "$HEADERS" | grep -qi "$header"; then
        echo -e "  ${GREEN}PASS${NC} Header: $header"
        PASS=$((PASS + 1))
    else
        echo -e "  ${YELLOW}WARN${NC} Missing header: $header"
        WARN=$((WARN + 1))
    fi
done
echo ""

# ==============================================================================
# Summary
# ==============================================================================

TOTAL=$((PASS + FAIL + WARN))
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$WARN warnings${NC} ($TOTAL total)"
echo ""

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}VERIFICATION FAILED${NC} — $FAIL critical issue(s) found"
    echo ""
    echo "Failed checks:"
    for r in "${RESULTS[@]}"; do
        if echo "$r" | grep -q "^FAIL|"; then
            echo "  - $(echo "$r" | cut -d'|' -f2): $(echo "$r" | cut -d'|' -f3)"
        fi
    done
    exit 1
elif [ $WARN -gt 0 ]; then
    echo -e "${YELLOW}VERIFICATION PASSED WITH WARNINGS${NC} — $WARN warning(s)"
    exit 0
else
    echo -e "${GREEN}ALL CHECKS PASSED${NC}"
    exit 0
fi
