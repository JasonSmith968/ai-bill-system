"""
Startup configuration validator for AI Accounting System.

Called at application startup (in create_app) to fail fast when secrets
are misconfigured.  Only enforces strict checks when FLASK_ENV=production.

Usage in app.py::

    from utils.startup_validator import validate_startup_config
    validate_startup_config(app)
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known placeholder / default values (case-insensitive)
# ---------------------------------------------------------------------------
_PLACEHOLDER_PATTERNS = (
    "change_me",
    "changeme",
    "your-secret-key",
    "dev-secret-key-not-for-production",
    "dev-jwt-secret-not-for-production",
    "test-secret-key",
    "test-jwt-secret-key",
    "example",
    "placeholder",
    "fill-me-in",
    "replace-me",
)

_DEFAULT_PASSWORDS = {
    "password", "123456", "admin123", "admin", "root",
    "password123", "12345678", "qwerty", "abc123",
    "letmein", "welcome", "monkey", "master",
    "exporter_password",
}

# Minimum lengths
_MIN_SECRET_LENGTH = 32
_MIN_PASSWORD_LENGTH = 24


def _is_placeholder(value: str) -> bool:
    """Return True if the value looks like a placeholder."""
    lowered = value.lower().strip()
    return any(p in lowered for p in _PLACEHOLDER_PATTERNS)


def _fail(message: str) -> None:
    """Print a clear error and exit."""
    print(f"\n{'='*70}", file=sys.stderr)
    print(f"[FATAL] Startup configuration error:", file=sys.stderr)
    print(f"  {message}", file=sys.stderr)
    print(f"{'='*70}\n", file=sys.stderr)
    sys.exit(1)


def validate_startup_config(app) -> None:
    """Validate critical configuration values at startup.

    In production mode (FLASK_ENV=production), this raises SystemExit(1)
    on any misconfiguration.  In development/testing, only warnings are
    logged.
    """
    is_production = (
        app.config.get("ENV") == "production"
        or os.environ.get("FLASK_ENV") == "production"
    )

    errors: list[str] = []

    # ------------------------------------------------------------------
    # 1. SECRET_KEY
    # ------------------------------------------------------------------
    secret_key = app.config.get("SECRET_KEY", "")
    if not secret_key:
        errors.append("SECRET_KEY is not set")
    elif _is_placeholder(secret_key):
        errors.append(f"SECRET_KEY appears to be a placeholder value")
    elif is_production and len(secret_key) < _MIN_SECRET_LENGTH:
        errors.append(f"SECRET_KEY is too short ({len(secret_key)} chars, minimum {_MIN_SECRET_LENGTH})")

    # ------------------------------------------------------------------
    # 2. JWT_SECRET_KEY
    # ------------------------------------------------------------------
    jwt_key = app.config.get("JWT_SECRET_KEY", "")
    if not jwt_key:
        errors.append("JWT_SECRET_KEY is not set")
    elif _is_placeholder(jwt_key):
        errors.append("JWT_SECRET_KEY appears to be a placeholder value")
    elif is_production and len(jwt_key) < _MIN_SECRET_LENGTH:
        errors.append(f"JWT_SECRET_KEY is too short ({len(jwt_key)} chars, minimum {_MIN_SECRET_LENGTH})")

    # ------------------------------------------------------------------
    # 3. SECRET_KEY and JWT_SECRET_KEY must differ
    # ------------------------------------------------------------------
    if secret_key and jwt_key and secret_key == jwt_key:
        errors.append("SECRET_KEY and JWT_SECRET_KEY must be different")

    # ------------------------------------------------------------------
    # 4. Production-only checks
    # ------------------------------------------------------------------
    if is_production:
        # DATABASE_URL
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if db_url:
            import re
            match = re.search(r"://[^:]+:([^@]+)@", db_url)
            if match:
                pwd = match.group(1).lower()
                for bad in _DEFAULT_PASSWORDS:
                    if bad in pwd:
                        errors.append(f"DATABASE_URL contains weak password component")
                        break
            if "change_me" in db_url.lower():
                errors.append("DATABASE_URL contains placeholder text")

        # ADMIN_PASSWORD (read from env, not from app config)
        admin_pwd = os.environ.get("ADMIN_PASSWORD", "")
        if admin_pwd and admin_pwd.lower() in _DEFAULT_PASSWORDS:
            errors.append("ADMIN_PASSWORD is set to a default value")

        # FERNET_KEY format
        fernet_key = app.config.get("FERNET_KEY", "")
        if fernet_key:
            import base64
            try:
                decoded = base64.urlsafe_b64decode(fernet_key)
                if len(decoded) != 32:
                    errors.append(f"FERNET_KEY decodes to {len(decoded)} bytes, expected 32")
            except Exception:
                errors.append("FERNET_KEY is not valid base64")

    # ------------------------------------------------------------------
    # 5. Report
    # ------------------------------------------------------------------
    if errors:
        if is_production:
            _fail("\n    ".join(errors))
        else:
            for e in errors:
                logger.warning(f"[startup_validator] {e}")
            logger.warning(
                "[startup_validator] %d issue(s) found in non-production mode "
                "-- these would be fatal in production", len(errors)
            )
    else:
        logger.info("[startup_validator] All configuration checks passed")
