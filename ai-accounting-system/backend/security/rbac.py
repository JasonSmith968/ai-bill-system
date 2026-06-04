"""Role-Based Access Control core logic."""

from functools import wraps
from flask import request, jsonify


def check_permission(user, permission_codename):
    """Check if a user has a specific permission."""
    if not user or not user.role:
        return False
    return user.has_permission(permission_codename)


def require_permission(permission_codename):
    """Decorator that requires a specific permission.

    Must be used after @token_required (or wraps it).
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # token_required should have already set request.current_user
            if not hasattr(request, 'current_user') or not request.current_user:
                return jsonify({'error': '未认证'}), 401

            if not check_permission(request.current_user, permission_codename):
                return jsonify({
                    'error': '权限不足',
                    'required': permission_codename
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def get_user_permissions(user):
    """Get all permission codenames for a user."""
    if not user or not user.role:
        return []
    return [p.codename for p in user.role.permissions]
