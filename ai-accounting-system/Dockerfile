# =============================================================================
# AI Accounting System - Combined Build (Security-Hardened)
# =============================================================================
# Builds frontend assets in a Node stage, then copies into the Python backend.
# Security measures:
#   - Multi-stage build (no Node.js in final image)
#   - Non-root user (appuser)
#   - Removed setuid/setgid binaries
#   - Read-only filesystem compatible (writable dirs via tmpfs volumes)
#   - Minimal attack surface
#
# To pin the base image digest for reproducibility, replace the tag with:
#   FROM node:20-alpine@sha256:<digest>
#   FROM python:3.12-slim@sha256:<digest>
# =============================================================================

# ---- Stage 1: Build frontend ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Production ----
FROM python:3.12-slim

# ---------- Create non-root user ----------
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# ---------- System deps ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# ---------- Python deps ----------
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Backend code ----------
COPY backend/ ./

# ---------- Frontend build output ----------
COPY --from=frontend-build /app/frontend/dist ./static

# ---------- Directories & permissions ----------
RUN mkdir -p uploads/avatars uploads/receipts logs \
    && chown -R appuser:appuser /app

# ---------- Remove setuid/setgid binaries (CIS Docker Benchmark 4.1) ----------
RUN find / -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

# ---------- Switch to non-root ----------
USER appuser

# ---------- Expose ----------
EXPOSE 5000

# ---------- Health check ----------
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# ---------- Run ----------
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:create_app()"]
