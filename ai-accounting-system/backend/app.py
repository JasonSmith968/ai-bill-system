import os
import logging
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, g, send_from_directory, Response
from flask_cors import CORS

from config import config
from extensions import db, migrate, limiter


def _init_sentry(app):
    """Initialize Sentry error tracking if DSN is configured."""
    dsn = app.config.get('SENTRY_DSN') or os.environ.get('SENTRY_DSN')
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.2,
            environment=app.config.get('FLASK_ENV', 'production'),
            release=os.environ.get('APP_VERSION', 'unknown'),
        )
        app.logger.info("Sentry initialized")
    except ImportError:
        app.logger.warning("sentry-sdk not installed, skipping Sentry init")


_prometheus_initialized = False


def _init_prometheus(app):
    """Initialize Prometheus metrics and /metrics endpoint."""
    global _prometheus_initialized
    try:
        from prometheus_client import (
            Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST,
        )

        # Avoid re-registration when create_app is called multiple times
        # (e.g. in tests).
        if _prometheus_initialized:
            return

        REQUEST_COUNT = Counter(
            'flask_request_total',
            'Total request count',
            ['method', 'endpoint', 'status']
        )
        REQUEST_LATENCY = Histogram(
            'flask_request_duration_seconds',
            'Request latency in seconds',
            ['method', 'endpoint'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        ACTIVE_REQUESTS = Gauge(
            'flask_active_requests',
            'Number of active requests'
        )

        @app.before_request
        def prometheus_before():
            ACTIVE_REQUESTS.inc()
            g._prom_start = datetime.utcnow()

        @app.after_request
        def prometheus_after(response):
            ACTIVE_REQUESTS.dec()
            if hasattr(g, '_prom_start'):
                duration = (datetime.utcnow() - g._prom_start).total_seconds()
                endpoint = request.endpoint or 'unknown'
                REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)
                REQUEST_COUNT.labels(
                    method=request.method,
                    endpoint=endpoint,
                    status=response.status_code
                ).inc()
            return response

        @app.route('/metrics')
        def metrics():
            # Auth guard: only allow internal/bearer access
            from flask import request as _req
            metrics_token = app.config.get('METRICS_AUTH_TOKEN')
            if metrics_token:
                auth = _req.headers.get('Authorization', '')
                if auth != f'Bearer {metrics_token}':
                    return Response('Forbidden', status=403)
            elif not app.debug:
                # Production without METRICS_AUTH_TOKEN configured — block access
                return Response('Forbidden', status=403)
            return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

        _prometheus_initialized = True
        app.logger.info("Prometheus metrics initialized at /metrics")
    except ImportError:
        app.logger.warning("prometheus-client not installed, skipping metrics")


def create_app(config_name='default'):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # --- Startup validation (fail fast on misconfigured secrets) ---
    from utils.startup_validator import validate_startup_config
    validate_startup_config(app)

    # --- Sentry (before extensions, catches init errors) ---
    _init_sentry(app)

    # --- Extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    CORS(app, origins=app.config['CORS_ORIGINS'])

    # --- Prometheus metrics ---
    _init_prometheus(app)

    # --- Logging ---
    from utils.logger import setup_logging
    setup_logging(app)

    # --- Request lifecycle hooks ---
    _register_request_hooks(app)

    # --- DB session observability ---
    from utils.db_observability import init_db_observability
    init_db_observability(app)

    # --- Security headers ---
    from middleware.security_headers import register_security_headers
    register_security_headers(app)

    # --- Tenant context middleware ---
    from middleware.tenant_context import init_tenant_context
    init_tenant_context(app)

    # --- Global error handlers ---
    _register_error_handlers(app)

    # --- Blueprints ---
    from routes.auth import auth_bp
    from routes.transactions import transactions_bp
    from routes.dashboard import dashboard_bp
    from routes.ai import ai_bp
    from routes.admin import admin_bp
    from routes.reports import reports_bp
    from routes.chat import chat_bp
    from routes.agent import agent_bp
    from routes.multi_agent import multi_agent_bp
    from routes.billing import billing_bp
    from routes.two_factor import two_factor_bp
    from routes.audit import audit_bp
    from routes.agent_v2 import agent_v2_bp
    from routes.tasks import tasks_bp
    from routes.bi import bi_bp
    from routes.tenant import tenant_bp
    from routes.analytics import analytics_bp
    from routes.model_router import router_bp
    from routes.growth import growth_bp
    from routes.cost_control import cost_control_bp
    from routes.retention_analytics import retention_bp
    from routes.admin_console import admin_console_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(transactions_bp, url_prefix='/api/transactions')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(agent_bp, url_prefix='/api/agent')
    app.register_blueprint(multi_agent_bp, url_prefix='/api/multi-agent')
    app.register_blueprint(billing_bp, url_prefix='/api/billing')
    app.register_blueprint(two_factor_bp, url_prefix='/api/auth/2fa')
    app.register_blueprint(audit_bp, url_prefix='/api/admin/audit-logs')
    app.register_blueprint(agent_v2_bp, url_prefix='/api/agent/v2')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    app.register_blueprint(bi_bp, url_prefix='/api/bi')
    app.register_blueprint(tenant_bp, url_prefix='/api/tenants')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(router_bp, url_prefix='/api/router')
    app.register_blueprint(growth_bp, url_prefix='/api/growth')
    app.register_blueprint(cost_control_bp, url_prefix='/api/cost-control')
    app.register_blueprint(retention_bp, url_prefix='/api/retention')
    app.register_blueprint(admin_console_bp, url_prefix='/api/admin/console')

    # --- Tenant query filter (auto-inject WHERE tenant_id) ---
    from models.tenant_query import setup_tenant_query_filter
    setup_tenant_query_filter()

    # --- Create tables (dev/testing only; production uses migrations) ---
    with app.app_context():
        import models  # noqa: F401 - registers all models

        if not app.config.get('TESTING') and app.config.get('DEBUG', False):
            db.create_all()

        # --- Seed default plans ---
        from models.plan import seed_plans
        seed_plans()

        # --- Seed roles and permissions ---
        from models.role import seed_roles_and_permissions
        seed_roles_and_permissions()

        # --- Migrate users to RBAC roles ---
        _migrate_users_to_roles()

        # --- Ensure all users have a tenant ---
        _ensure_user_tenants(app)

        # --- Initialize Agent Manager ---
        from agents import get_manager
        get_manager()

        # --- Initialize Agent Hardening Components ---
        from agents.circuit_breaker import get_all_breakers
        from agents.llm_tracer import get_tracer
        from agents.prompt_registry import get_prompt_registry
        from agents.context_compressor import get_compressor
        from agents.monitoring import get_monitor
        app.logger.info("Agent hardening components initialized")

        # --- Initialize Celery ---
        from celery_app import make_celery
        make_celery(app)

        # --- Initialize Cache ---
        from cache import init_cache
        init_cache(app)

        # --- Initialize SocketIO ---
        from websocket import init_socketio
        init_socketio(app)

    # --- Upload directory (local storage needs these) ---
    upload_dir = os.path.join(app.root_path, 'uploads')
    os.makedirs(os.path.join(upload_dir, 'receipts'), exist_ok=True)
    os.makedirs(os.path.join(upload_dir, 'avatars'), exist_ok=True)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    # --- Serve uploaded files (local storage) ---
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        storage_provider = app.config.get('STORAGE_PROVIDER', 'local')
        if storage_provider == 'local':
            return send_from_directory(upload_dir, filename)
        # Cloud storage: redirect to presigned URL
        from services.storage import get_storage
        url = get_storage().get_url(filename)
        return '', 302, {'Location': url}

    # --- Health check ---
    @app.route('/health')
    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})

    app.logger.info("Application started successfully")
    return app


def _migrate_users_to_roles():
    """One-time migration: assign roles to existing users based on is_admin flag."""
    from models.user import User
    from models.role import Role

    users_without_role = User.query.filter(User.role_id.is_(None)).all()
    if not users_without_role:
        return

    owner_role = Role.query.filter_by(name='owner').first()
    member_role = Role.query.filter_by(name='member').first()

    if not owner_role or not member_role:
        return

    for user in users_without_role:
        user.role_id = owner_role.id if user.is_admin else member_role.id

    db.session.commit()


def _ensure_user_tenants(app):
    """Startup check: ensure all users have a tenant. Auto-creates one for orphaned users."""
    from models.user import User
    from services.tenant_service import create_tenant

    orphaned = User.query.filter(User.tenant_id.is_(None)).all()
    if not orphaned:
        return

    for user in orphaned:
        tenant, _ = create_tenant(f"{user.username}的工作区", user.id)
        if tenant:
            user.tenant_id = tenant.id
            app.logger.info(f"Auto-created tenant for orphaned user: {user.id}")

    db.session.commit()


def _register_request_hooks(app):
    """Register before/after request hooks for logging and timing."""

    @app.before_request
    def before_request():
        g.start_time = datetime.utcnow()
        g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4())[:8])

    @app.after_request
    def after_request(response):
        # Return the scoped session to the pool so the next request gets a
        # clean session.  This prevents stale ORM identity-map references
        # (e.g. ObjectDeletedError) when an object is modified/deleted by
        # a concurrent request or background task.  It is *not* a substitute
        # for proper category validation — that is handled at the route level.
        try:
            db.session.remove()
        except Exception:
            pass

        # Skip logging for static assets and health checks
        if request.path.startswith('/static') or request.path == '/health':
            return response

        duration = 0
        if hasattr(g, 'start_time'):
            duration = (datetime.utcnow() - g.start_time).total_seconds() * 1000

        access_logger = logging.getLogger('access')
        access_logger.info(
            f"{request.remote_addr} {request.method} {request.path} "
            f"{response.status_code} {duration:.0f}ms"
        )

        # Add request ID header (security headers handled by middleware)
        response.headers['X-Request-ID'] = g.get('request_id', '')

        return response


def _register_error_handlers(app):
    """Register global JSON error handlers."""

    def _error_response(status_code, message, detail=None):
        payload = {
            'error': message,
            'status_code': status_code,
            'request_id': g.get('request_id', ''),
        }
        if detail:
            payload['detail'] = detail
        return jsonify(payload), status_code

    @app.errorhandler(400)
    def bad_request(e):
        return _error_response(400, '请求参数错误', str(e.description))

    @app.errorhandler(401)
    def unauthorized(e):
        return _error_response(401, '未授权访问')

    @app.errorhandler(403)
    def forbidden(e):
        return _error_response(403, '权限不足')

    @app.errorhandler(404)
    def not_found(e):
        return _error_response(404, '资源不存在')

    @app.errorhandler(405)
    def method_not_allowed(e):
        return _error_response(405, '请求方法不允许')

    @app.errorhandler(429)
    def rate_limited(e):
        app.logger.warning(f"Rate limit exceeded: {request.remote_addr} {request.method} {request.path}")
        return _error_response(429, '请求过于频繁，请稍后再试')

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"Internal server error: {e}", exc_info=True)
        db.session.rollback()
        return _error_response(500, '服务器内部错误')

    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f"Unhandled exception: {e}", exc_info=True)
        db.session.rollback()
        return _error_response(500, '服务器内部错误')


if __name__ == '__main__':
    app = create_app()
    from websocket import socketio
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
