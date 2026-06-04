#!/bin/bash
# Full Production Load Test Suite
# Runs all 7 test scenarios and generates comprehensive results
#
# Usage:
#   ./tests/load/run_all.sh [BASE_URL]
#
# Requires: k6, python3 (for system monitor)

set -euo pipefail

BASE_URL="${1:-http://localhost:5000}"
RESULTS_DIR="tests/load/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
K6="./tests/load/k6.exe"

# Use local k6 if available, otherwise system k6
if [ -f "$K6" ]; then
    K6_CMD="$K6"
elif command -v k6 &> /dev/null; then
    K6_CMD="k6"
else
    echo "ERROR: k6 not found. Place k6.exe in tests/load/ or install globally."
    exit 1
fi

mkdir -p "$RESULTS_DIR"

echo "============================================"
echo " AI Accounting System — Full Load Test Suite"
echo "============================================"
echo "Target:   $BASE_URL"
echo "Results:  $RESULTS_DIR/"
echo "k6:       $K6_CMD"
echo "Timestamp: $TIMESTAMP"
echo ""

# Check server is up
if ! curl -sf "$BASE_URL/health" > /dev/null 2>&1; then
    echo "ERROR: Server not responding at $BASE_URL/health"
    exit 1
fi
echo "Server: OK"
echo ""

# Start system monitor in background (if Python available)
MONITOR_PID=""
if command -v python &> /dev/null || command -v python3 &> /dev/null; then
    PY_CMD=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
    echo "Starting system monitor..."
    $PY_CMD tests/load/monitor.py --duration 900 --interval 5 \
        --output "$RESULTS_DIR/system_metrics_${TIMESTAMP}.json" &
    MONITOR_PID=$!
    echo "Monitor PID: $MONITOR_PID"
fi

# ── Test Scenarios ──────────────────────────────────────────────────────

TESTS=(
    "test_concurrency_ramp:1. API Baseline (100→300→500→1000 VUs)"
    "test_db_writes:2. Database Write Stress (400 VUs concurrent writes)"
    "test_redis_stress:3. Redis Cache Stress (500 VUs, cache hit/miss)"
    "test_ai:4. AI Endpoint Stress (20 VUs LLM calls)"
    "test_websocket:5. WebSocket Stress (100 connections)"
    "test_celery_stress:6. Celery Queue Stress (200 VUs task submission)"
    "test_stripe_webhook:7. Stripe Webhook Flood (100 VUs idempotency)"
)

FAILED=0
PASSED=0
TOTAL=${#TESTS[@]}

for entry in "${TESTS[@]}"; do
    IFS=':' read -r test_file test_name <<< "$entry"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " $test_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if $K6_CMD run \
        --env BASE_URL="$BASE_URL" \
        --summary-export="$RESULTS_DIR/${test_file}_summary_${TIMESTAMP}.json" \
        "tests/load/${test_file}.js" 2>&1 | tee "$RESULTS_DIR/${test_file}_output_${TIMESTAMP}.txt"; then
        echo "PASS: $test_name"
        PASSED=$((PASSED + 1))
    else
        echo "FAIL: $test_name"
        FAILED=$((FAILED + 1))
    fi

    # Cool-down between tests
    echo "Cooling down (10s)..."
    sleep 10
done

# ── Stop Monitor ────────────────────────────────────────────────────────

if [ -n "$MONITOR_PID" ]; then
    echo ""
    echo "Stopping system monitor..."
    kill "$MONITOR_PID" 2>/dev/null || true
    wait "$MONITOR_PID" 2>/dev/null || true
fi

# ── Summary ─────────────────────────────────────────────────────────────

echo ""
echo "============================================"
echo " Load Test Summary"
echo "============================================"
echo "Total:  $TOTAL scenarios"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""
echo "Results directory: $RESULTS_DIR/"
echo ""

# List result files
echo "Generated files:"
ls -la "$RESULTS_DIR/"*_${TIMESTAMP}* 2>/dev/null || echo "  (no files)"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "WARNING: $FAILED scenario(s) failed. Review results."
    exit 1
else
    echo ""
    echo "All load test scenarios passed."
    exit 0
fi
