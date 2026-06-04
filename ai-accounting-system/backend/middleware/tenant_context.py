"""Tenant context middleware — resolves tenant from JWT or subdomain on every request."""

import logging
from functools import wraps
from flask import request, g, jsonify

logger = logging.getLogger(__name__)

# Endpoints that do NOT require tenant context
_TENANT_SKIP_PATHS = (
    '/health',
    '/metrics',
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/refresh',
    '/api/auth/forgot-password',
    '/api/auth/reset-password',
    '/api/auth/verify-email',
    '/api/auth/resend-verification',
    '/api/billing/plans',
    '/api/billing/webhook/',
    '/uploads/',
    '/static/',
)


def init_tenant_context(app):
    """Register before_request hook that sets g.current_tenant."""

    @app.before_request
    def resolve_tenant():
        # Skip for paths that don't need tenant context
        path = request.path
        if any(path.startswith(p) for p in _TENANT_SKIP_PATHS):
            return None

        # Skip for OPTIONS (CORS preflight)
        if request.method == 'OPTIONS':
            return None

        # 1. Try JWT claim first (most common case)
        tenant_id = _resolve_tenant_from_jwt()
        if tenant_id:
            _set_current_tenant(tenant_id)
            return None

        # 2. Try subdomain
        tenant_slug = _resolve_tenant_from_subdomain()
        if tenant_slug:
            _set_current_tenant_by_slug(tenant_slug)
            return None

        # 3. No tenant context found — for authenticated endpoints this is an error
        # (unauthenticated endpoints like /api/auth/* are already skipped above)
        if _is_authenticated_request():
            return jsonify({'error': '租户上下文缺失，请提供有效的 tenant_id'}), 401

        return None


def _resolve_tenant_from_jwt():
    """Extract tenant_id from the JWT payload in the Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]
    try:
        import jwt as pyjwt
        from flask import current_app
        payload = pyjwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload.get('tenant_id')
    except Exception:
        return None


def _resolve_tenant_from_subdomain():
    """Extract tenant slug from subdomain (e.g., acme.app.com -> 'acme')."""
    host = request.host  # e.g., 'acme.app.com' or 'localhost:5000'
    parts = host.split('.')
    # Need at least 3 parts for subdomain (subdomain.domain.tld)
    if len(parts) >= 3:
        slug = parts[0]
        # Skip 'www' and common non-tenant prefixes
        if slug not in ('www', 'api', 'admin'):
            return slug
    return None


def _set_current_tenant(tenant_id):
    """Load tenant and verify membership, set g.current_tenant and g.tenant_role."""
    from models.tenant import Tenant, TenantMember
    from models.user import User

    tenant = Tenant.query.get(tenant_id)
    if not tenant or tenant.status != 'active':
        g.current_tenant = None
        g.tenant_role = None
        return

    # Verify the current user is a member of this tenant
    user_id = getattr(request, 'current_user', None)
    if user_id:
        user_id = user_id.id if hasattr(user_id, 'id') else None

    if user_id:
        membership = TenantMember.query.filter_by(
            tenant_id=tenant.id, user_id=user_id
        ).first()
        if membership:
            g.current_tenant = tenant
            g.tenant_role = membership.role
        else:
            g.current_tenant = None
            g.tenant_role = None
    else:
        # For requests where user isn't resolved yet (e.g. before token_required)
        # just set the tenant; membership will be checked by decorators
        g.current_tenant = tenant
        g.tenant_role = None


def _set_current_tenant_by_slug(slug):
    """Load tenant by slug."""
    from models.tenant import Tenant
    tenant = Tenant.query.filter_by(slug=slug, status='active').first()
    if tenant:
        g.current_tenant = tenant
    else:
        g.current_tenant = None
    g.tenant_role = None


def _is_authenticated_request():
    """Check if the request has an Authorization header."""
    return 'Authorization' in request.headers


def require_tenant(f):
    """Decorator: ensures current request has a valid tenant context."""
    @wraps(f)
    def decorated(*args, **kwargs):
        tenant = getattr(g, 'current_tenant', None)
        if not tenant:
            return jsonify({'error': '需要有效的租户上下文'}), 403
        return f(*args, **kwargs)
    return decorated


def require_tenant_role(*roles):
    """Decorator: ensures user has one of the specified roles within the current tenant.

    Usage:
        @require_tenant_role('owner', 'admin')
        def manage_members():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                return jsonify({'error': '需要有效的租户上下文'}), 403

            role = getattr(g, 'tenant_role', None)
            if role not in roles:
                return jsonify({'error': f'需要以下角色之一: {", ".join(roles)}'}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator
