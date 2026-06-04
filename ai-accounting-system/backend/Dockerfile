# =============================================================================
# AI Accounting System - Backend (Security-Hardened)
# =============================================================================
# Security measures:
#   - Non-root user (appuser)
#   - Removed setuid/setgid binaries
#   - Read-only filesystem compatible (writable dirs via tmpfs volumes)
#   - Minimal attack surface (no-install-recommends, cleaned apt lists)
#   - Health check for container orchestration
#
# To pin the base image digest for reproducibility, replace the tag with:
#   FROM python:3.12-slim@sha256:<digest>
# Get the digest: docker pull python:3.12-slim && docker inspect --format='{{index .RepoDigests 0}}' python:3.12-slim
# =============================================================================

FROM python:3.12-slim

# ---------- Create non-root user early ----------
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# ---------- System deps ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ---------- Python deps (as root, cached layer) ----------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- App code ----------
COPY . .

# ---------- Directories & permissions ----------
RUN mkdir -p uploads/avatars uploads/receipts logs \
    && chown -R appuser:appuser /app \
    && chmod +x entrypoint.sh

# ---------- Remove setuid/setgid binaries (CIS Docker Benchmark 4.1) ----------
RUN find / -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

# ---------- Switch to non-root ----------
USER appuser

# ---------- Expose ----------
EXPOSE 5000

# ---------- Health check ----------
# --cap-drop=ALL is set in docker-compose.security.yml
# --security-opt=no-new-privileges is set in docker-compose.security.yml
# --read-only is set in docker-compose.security.yml (tmpfs mounts for writable dirs)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# ---------- Entrypoint ----------
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "--timeout", "120", "-k", "eventlet", "app:create_app()"]
