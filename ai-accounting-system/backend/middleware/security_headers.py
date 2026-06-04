"""Enhanced security headers middleware."""

from flask import request


def register_security_headers(app):
    """Register enhanced security headers on the Flask app."""

    @app.after_request
    def add_security_headers(response):
        # Skip for static assets
        if request.path.startswith('/static'):
            return response

        # Existing headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Enhanced headers
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        # HSTS (only in production over HTTPS)
        if not app.debug and request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # CSP - permissive for dev, should be tightened in production
        if app.debug:
            response.headers['Content-Security-Policy'] = (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
                "img-src 'self' data: https:; "
                "connect-src 'self' http://localhost:* ws://localhost:*"
            )
        else:
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self'"
            )

        return response
