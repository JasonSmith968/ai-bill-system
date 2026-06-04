#!/bin/bash
set -e

# ============================================================
# AI Accounting System — Database Backup Script
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
RETENTION_DAYS=7

# Load env
if [ -f "${PROJECT_DIR}/.env.production" ]; then
    export $(grep -v '^#' "${PROJECT_DIR}/.env.production" | xargs)
fi

MYSQL_USER="${MYSQL_USER:-ai_user}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-ai_password}"
MYSQL_DATABASE="${MYSQL_DATABASE:-ai_accounting}"
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${MYSQL_DATABASE}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup of ${MYSQL_DATABASE}..."

# Run mysqldump inside the mysql container
docker exec ai-mysql mysqldump \
    -u root \
    -p"${MYSQL_ROOT_PASSWORD}" \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    "${MYSQL_DATABASE}" | gzip > "${BACKUP_FILE}"

FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup created: ${BACKUP_FILE} (${FILESIZE})"

# Clean up old backups
echo "[$(date)] Cleaning backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete 2>/dev/null || true

REMAINING=$(find "$BACKUP_DIR" -name "*.sql.gz" | wc -l)
echo "[$(date)] Backup complete. ${REMAINING} backup(s) on disk."

# Optional: Upload to S3/OSS
# if command -v aws &> /dev/null; then
#     aws s3 cp "$BACKUP_FILE" s3://your-bucket/backups/
#     echo "[$(date)] Uploaded to S3"
# fi
