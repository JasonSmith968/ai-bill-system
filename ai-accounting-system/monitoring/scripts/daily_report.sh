#!/usr/bin/env bash
# ==============================================================================
# AI Accounting System — Daily Production Report Generator
# ==============================================================================
# Run via cron: 0 8 * * * /opt/ai-accounting-system/monitoring/scripts/daily_report.sh
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="$PROJECT_DIR/monitoring/reports"
DATE="$(date +%Y%m%d)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

# Ensure report directory exists
mkdir -p "$REPORT_DIR"

# Generate reports
echo "[$(date)] Generating daily production report..."

# Text report (for email/console)
python "$SCRIPT_DIR/production_metrics.py" \
    --output report \
    --period 1d \
    --save "$REPORT_DIR/report-${DATE}.txt"

# JSON report (for dashboards/automation)
python "$SCRIPT_DIR/production_metrics.py" \
    --output json \
    --period 1d \
    --save "$REPORT_DIR/report-${DATE}.json"

# 7-day report (weekly summary)
python "$SCRIPT_DIR/production_metrics.py" \
    --output json \
    --period 7d \
    --save "$REPORT_DIR/report-${DATE}-7d.json"

echo "[$(date)] Reports saved to $REPORT_DIR/"

# Cleanup old reports (keep 90 days)
find "$REPORT_DIR" -name "report-*.txt" -mtime +90 -delete 2>/dev/null || true
find "$REPORT_DIR" -name "report-*.json" -mtime +90 -delete 2>/dev/null || true

# Optional: send report via email
# if command -v mail &> /dev/null; then
#     mail -s "AI Accounting Daily Report $DATE" ops@company.com < "$REPORT_DIR/report-${DATE}.txt"
# fi

echo "[$(date)] Daily report generation complete."
