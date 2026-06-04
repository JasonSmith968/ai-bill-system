#!/bin/bash
# =============================================================================
# AI Accounting System - Docker Security Scan
# =============================================================================
# Scans all containers and images for common security issues.
# Usage: ./scripts/docker_security_scan.sh [--image-scan] [--full]
#
# Requirements:
#   - Docker CLI
#   - Optional: trivy (https://github.com/aquasecurity/trivy)
#   - Optional: docker scout (Docker Desktop or docker scout plugin)
# =============================================================================

set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Configuration ---
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-ai-accounting-system}"
REPORT_FILE="security-report-$(date +%Y%m%d-%H%M%S).txt"
IMAGE_SCAN=false
FULL_SCAN=false

# --- Parse args ---
for arg in "$@"; do
    case $arg in
        --image-scan) IMAGE_SCAN=true ;;
        --full) FULL_SCAN=true; IMAGE_SCAN=true ;;
        --help|-h)
            echo "Usage: $0 [--image-scan] [--full]"
            echo "  --image-scan  Run vulnerability scan on images (requires trivy or docker scout)"
            echo "  --full        Full scan including image vulnerabilities"
            exit 0
            ;;
    esac
done

# --- Counters ---
PASS=0
WARN=0
FAIL=0

# --- Helpers ---
log_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

log_pass() {
    echo -e "  ${GREEN}[PASS]${NC} $1"
    PASS=$((PASS + 1))
}

log_warn() {
    echo -e "  ${YELLOW}[WARN]${NC} $1"
    WARN=$((WARN + 1))
}

log_fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
    FAIL=$((FAIL + 1))
}

log_info() {
    echo -e "  ${BLUE}[INFO]${NC} $1"
}

# --- Start report ---
{
    echo "AI Accounting System - Docker Security Report"
    echo "Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "Host: $(hostname)"
    echo "Docker: $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'unknown')"
    echo ""
} | tee "$REPORT_FILE"

# =========================================================================
log_header "1. Container Runtime Security"
# =========================================================================

# Get all running containers for this project
CONTAINERS=$(docker ps --filter "label=com.docker.compose.project=${PROJECT_NAME}" --format '{{.Names}}' 2>/dev/null || true)

if [ -z "$CONTAINERS" ]; then
    # Fallback: check by known container names
    CONTAINERS=$(docker ps --format '{{.Names}}' | grep -E '^ai-' 2>/dev/null || true)
fi

if [ -z "$CONTAINERS" ]; then
    log_warn "No running containers found. Start the stack first: docker compose -f docker-compose.prod.yml up -d"
else
    for CONTAINER in $CONTAINERS; do
        echo ""
        log_info "Checking container: $CONTAINER"

        # --- Check if running as root ---
        USER=$(docker exec "$CONTAINER" whoami 2>/dev/null || echo "unknown")
        if [ "$USER" = "root" ]; then
            log_fail "$CONTAINER: Running as root user"
        else
            log_pass "$CONTAINER: Running as non-root user ($USER)"
        fi

        # --- Check for privileged mode ---
        PRIVILEGED=$(docker inspect --format='{{.HostConfig.Privileged}}' "$CONTAINER" 2>/dev/null || echo "unknown")
        if [ "$PRIVILEGED" = "true" ]; then
            log_fail "$CONTAINER: Running in privileged mode"
        else
            log_pass "$CONTAINER: Not running in privileged mode"
        fi

        # --- Check for host network mode ---
        NETWORK_MODE=$(docker inspect --format='{{.HostConfig.NetworkMode}}' "$CONTAINER" 2>/dev/null || echo "unknown")
        if [ "$NETWORK_MODE" = "host" ]; then
            log_fail "$CONTAINER: Using host network mode"
        else
            log_pass "$CONTAINER: Using isolated network mode ($NETWORK_MODE)"
        fi

        # --- Check for no-new-privileges ---
        SECURITY_OPT=$(docker inspect --format='{{.HostConfig.SecurityOpt}}' "$CONTAINER" 2>/dev/null || echo "[]")
        if echo "$SECURITY_OPT" | grep -q "no-new-privileges"; then
            log_pass "$CONTAINER: no-new-privileges is set"
        else
            log_warn "$CONTAINER: no-new-privileges not set"
        fi

        # --- Check for cap-drop ALL ---
        CAP_DROP=$(docker inspect --format='{{.HostConfig.CapDrop}}' "$CONTAINER" 2>/dev/null || echo "[]")
        if echo "$CAP_DROP" | grep -qi "ALL"; then
            log_pass "$CONTAINER: All capabilities dropped (cap_drop=ALL)"
        else
            log_warn "$CONTAINER: Not all capabilities dropped"
        fi

        # --- Check for read-only root filesystem ---
        READ_ONLY=$(docker inspect --format='{{.HostConfig.ReadonlyRootfs}}' "$CONTAINER" 2>/dev/null || echo "unknown")
        if [ "$READ_ONLY" = "true" ]; then
            log_pass "$CONTAINER: Read-only root filesystem"
        else
            log_warn "$CONTAINER: Root filesystem is writable"
        fi

        # --- Check for resource limits ---
        MEMORY_LIMIT=$(docker inspect --format='{{.HostConfig.Memory}}' "$CONTAINER" 2>/dev/null || echo "0")
        CPU_LIMIT=$(docker inspect --format='{{.HostConfig.NanoCpus}}' "$CONTAINER" 2>/dev/null || echo "0")
        if [ "$MEMORY_LIMIT" != "0" ] && [ "$MEMORY_LIMIT" != "" ]; then
            MEMORY_MB=$((MEMORY_LIMIT / 1024 / 1024))
            log_pass "$CONTAINER: Memory limit set (${MEMORY_MB}MB)"
        else
            log_warn "$CONTAINER: No memory limit set"
        fi
        if [ "$CPU_LIMIT" != "0" ] && [ "$CPU_LIMIT" != "" ]; then
            log_pass "$CONTAINER: CPU limit set"
        else
            log_warn "$CONTAINER: No CPU limit set"
        fi

        # --- Check for PID limit ---
        PID_LIMIT=$(docker inspect --format='{{.HostConfig.PidsLimit}}' "$CONTAINER" 2>/dev/null || echo "0")
        if [ "$PID_LIMIT" != "0" ] && [ "$PID_LIMIT" != "-1" ] && [ -n "$PID_LIMIT" ]; then
            log_pass "$CONTAINER: PID limit set ($PID_LIMIT)"
        else
            log_warn "$CONTAINER: No PID limit (consider setting pids_limit)"
        fi

        # --- Check exposed ports ---
        PORTS=$(docker port "$CONTAINER" 2>/dev/null || echo "none")
        if [ "$PORTS" = "none" ] || [ -z "$PORTS" ]; then
            log_pass "$CONTAINER: No exposed ports to host"
        else
            # Check if bound to 0.0.0.0
            if echo "$PORTS" | grep -q "0.0.0.0"; then
                log_warn "$CONTAINER: Ports bound to 0.0.0.0 (all interfaces): $PORTS"
            else
                log_pass "$CONTAINER: Ports bound to localhost only"
            fi
        fi
    done
fi

# =========================================================================
log_header "2. Docker Daemon Configuration"
# =========================================================================

# Check if Docker socket is mounted in any container
if [ -n "$CONTAINERS" ]; then
    for CONTAINER in $CONTAINERS; do
        DOCKER_SOCKET=$(docker inspect "$CONTAINER" --format='{{range .Mounts}}{{.Source}} {{end}}' 2>/dev/null || echo "")
        if echo "$DOCKER_SOCKET" | grep -q "docker.sock"; then
            log_fail "$CONTAINER: Docker socket is mounted (container escape risk)"
        fi
    done
fi

# Check Docker content trust
if [ "${DOCKER_CONTENT_TRUST:-0}" = "1" ]; then
    log_pass "DOCKER_CONTENT_TRUST is enabled"
else
    log_warn "DOCKER_CONTENT_TRUST is not set (consider enabling for image signing)"
fi

# Check Docker logging driver
LOG_DRIVER=$(docker info --format '{{.LoggingDriver}}' 2>/dev/null || echo "unknown")
log_info "Default logging driver: $LOG_DRIVER"

# =========================================================================
log_header "3. Image Security"
# =========================================================================

IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '(ai-accounting|ai_backend|ai_frontend|ai-)' 2>/dev/null || true)

if [ -z "$IMAGES" ]; then
    log_info "No project-specific images found"
else
    for IMAGE in $IMAGES; do
        echo ""
        log_info "Checking image: $IMAGE"

        # Check if image has a HEALTHCHECK
        HC=$(docker inspect "$IMAGE" --format='{{json .Config.Healthcheck}}' 2>/dev/null || echo "null")
        if [ "$HC" = "null" ] || [ "$HC" = "{}" ] || [ -z "$HC" ]; then
            log_warn "$IMAGE: No HEALTHCHECK defined"
        else
            log_pass "$IMAGE: HEALTHCHECK defined"
        fi

        # Check default user
        IMG_USER=$(docker inspect "$IMAGE" --format='{{.Config.User}}' 2>/dev/null || echo "")
        if [ -z "$IMG_USER" ] || [ "$IMG_USER" = "root" ] || [ "$IMG_USER" = "0" ]; then
            log_warn "$IMAGE: Default user is root"
        else
            log_pass "$IMAGE: Default user is non-root ($IMG_USER)"
        fi
    done
fi

# =========================================================================
log_header "4. Network Isolation"
# =========================================================================

NETWORKS=$(docker network ls --format '{{.Name}}' | grep -E '(ai-accounting|backend|frontend|monitoring|elk)' 2>/dev/null || true)

if [ -n "$NETWORKS" ]; then
    for NET in $NETWORKS; do
        INTERNAL=$(docker network inspect "$NET" --format='{{.Internal}}' 2>/dev/null || echo "false")
        if [ "$INTERNAL" = "true" ]; then
            log_pass "Network '$NET' is internal (no external access)"
        else
            if echo "$NET" | grep -qi "frontend"; then
                log_pass "Network '$NET' is external (expected for frontend)"
            else
                log_warn "Network '$NET' is not internal"
            fi
        fi
    done
else
    log_info "No project networks found"
fi

# =========================================================================
log_header "5. Volume Mounts"
# =========================================================================

if [ -n "$CONTAINERS" ]; then
    for CONTAINER in $CONTAINERS; do
        # Check for sensitive host mounts
        MOUNTS=$(docker inspect "$CONTAINER" --format='{{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}' 2>/dev/null || echo "")
        if echo "$MOUNTS" | grep -qE '/etc/shadow|/etc/passwd|/root'; then
            log_fail "$CONTAINER: Sensitive host path mounted"
        fi
        if echo "$MOUNTS" | grep -q "\.env"; then
            log_warn "$CONTAINER: .env file mounted (ensure no secrets in plaintext)"
        fi
    done
fi

# =========================================================================
# Image vulnerability scanning (optional)
# =========================================================================

if [ "$IMAGE_SCAN" = true ]; then
    log_header "6. Image Vulnerability Scan"

    if command -v trivy &>/dev/null; then
        log_info "Using trivy for vulnerability scanning..."
        for IMAGE in ${IMAGES:-}; do
            echo ""
            log_info "Scanning $IMAGE..."
            trivy image --severity HIGH,CRITICAL --no-progress "$IMAGE" 2>&1 | head -50
        done
    elif command -v docker &>/dev/null && docker scout version &>/dev/null 2>&1; then
        log_info "Using Docker Scout for vulnerability scanning..."
        for IMAGE in ${IMAGES:-}; do
            echo ""
            log_info "Scanning $IMAGE..."
            docker scout cves "$IMAGE" --only-severity critical,high 2>&1 | head -50
        done
    else
        log_warn "No image scanner found. Install trivy or enable Docker Scout."
        log_info "  trivy: https://github.com/aquasecurity/trivy#installation"
        log_info "  Docker Scout: https://docs.docker.com/scout/"
    fi
fi

# =========================================================================
# Summary
# =========================================================================

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Security Scan Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "  ${GREEN}PASS:${NC} $PASS"
echo -e "  ${YELLOW}WARN:${NC} $WARN"
echo -e "  ${RED}FAIL:${NC} $FAIL"
echo ""

{
    echo ""
    echo "=== Summary ==="
    echo "PASS: $PASS"
    echo "WARN: $WARN"
    echo "FAIL: $FAIL"
} >> "$REPORT_FILE"

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Security issues found. Review the report: $REPORT_FILE${NC}"
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo -e "${YELLOW}Warnings found. Consider addressing them. Report: $REPORT_FILE${NC}"
    exit 0
else
    echo -e "${GREEN}All checks passed. Report saved: $REPORT_FILE${NC}"
    exit 0
fi
