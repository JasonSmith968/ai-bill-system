# =============================================================================
# AI Accounting System - Frontend (Security-Hardened)
# =============================================================================
# Security measures:
#   - Multi-stage build (no build tools in final image)
#   - Explicit non-root USER nginx
#   - Server tokens hidden
#   - Proper file permissions on static assets
#   - Read-only filesystem compatible (tmpfs for nginx caches)
#
# To pin the base image digest for reproducibility, replace the tag with:
#   FROM node:20-alpine@sha256:<digest>
#   FROM nginx:alpine@sha256:<digest>
# Get digests: docker pull <image> && docker inspect --format='{{index .RepoDigests 0}}' <image>
# =============================================================================

# ---- Stage 1: Build ----
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- Stage 2: Serve with Nginx ----
FROM nginx:alpine

# Remove default config and server token disclosure
RUN rm /etc/nginx/conf.d/default.conf \
    && echo "server_tokens off;" > /etc/nginx/conf.d/security.conf

# Copy custom nginx config for SPA
COPY nginx.conf /etc/nginx/conf.d/frontend.conf

# Copy built assets and set permissions
COPY --from=build /app/dist /usr/share/nginx/html
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chmod -R 755 /usr/share/nginx/html

# Ensure nginx temp directories exist with correct ownership
RUN mkdir -p /var/cache/nginx /var/run \
    && chown -R nginx:nginx /var/cache/nginx /var/run

# Explicitly switch to non-root user
# nginx:alpine already has nginx user, but we set it explicitly for clarity
USER nginx

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:80/ || exit 1

EXPOSE 80
