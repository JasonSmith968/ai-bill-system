#!/usr/bin/env python3
"""
Validate production secrets for AI Accounting System.

Usage:
    python scripts/validate_secrets.py                         # Validate .env.production
    python scripts/validate_secrets.py --env-file path/to/.env # Validate specific file
    python scripts/validate_secrets.py --from-env              # Validate OS environment variables

Exit codes:
    0 = all checks passed
    1 = one or more checks failed (detailed errors printed)

Only uses Python standard library.
"""

import argparse
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Known bad / placeholder values (lowercased, stripped of underscores/hyphens)
# ---------------------------------------------------------------------------
KNOWN_BAD_VALUES = {
    "change_me", "changeme", "password", "123456", "admin123",
    "secret", "test", "default", "example", "your-secret-key",
    "change_me_generate_with_python_-c_secrets_token_hex_32",
    "sk-change_me_rotate_after_compromise",
    "exporter_password", "admin", "root", "toor",
    "password123", "12345678", "qwerty", "abc123",
    "letmein", "welcome", "monkey", "master",
}


def _normalise(value: str) -> str:
    """Lowercase and strip common separators for comparison."""
    return value.lower().replace("_", "").replace("-", "").strip()


# ---------------------------------------------------------------------------
# Check definitions
# ---------------------------------------------------------------------------

# (env_var, min_length, description)
SECRET_CHECKS: list[tuple[str, int, str]] = [
    ("SECRET_KEY",              64, "Flask session signing key (expect 64 hex chars)"),
    ("JWT_SECRET_KEY",          64, "JWT signing key (expect 64 hex chars)"),
    ("FERNET_KEY",              32, "Fernet encryption key (base64, >= 32 chars)"),
    ("MYSQL_ROOT_PASSWORD",     32, "MySQL root password"),
    ("MYSQL_PASSWORD",          32, "MySQL application password"),
    ("REDIS_PASSWORD",          32, "Redis password"),
    ("ADMIN_PASSWORD",          24, "Admin user password"),
    ("MYSQL_EXPORTER_PASSWORD", 24, "MySQL exporter password"),
    ("GRAFANA_PASSWORD",        24, "Grafana admin password"),
    ("METRICS_AUTH_TOKEN",      64, "Prometheus metrics bearer token"),
    ("REQUEST_SIGNING_SECRET",  64, "Request HMAC signing secret"),
]

# Non-secret required vars
REQUIRED_VARS: list[str] = [
    "DATABASE_URL",
    "REDIS_URL",
    "FLASK_ENV",
]


def _load_env_file(path: str) -> dict[str, str]:
    """Parse a .env file into a dict."""
    env: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return env
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def _get_env(source: str | None, from_os: bool) -> dict[str, str]:
    """Load environment variables from file or OS."""
    if from_os:
        return dict(os.environ)
    path = source or str(Path(__file__).resolve().parent.parent / ".env.production")
    return _load_env_file(path)


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def validate(env: dict[str, str], *, strict: bool = True) -> ValidationResult:
    """Run all validation checks. Returns a ValidationResult."""
    result = ValidationResult()

    # ------------------------------------------------------------------
    # 1. Required non-secret vars
    # ------------------------------------------------------------------
    for var in REQUIRED_VARS:
        val = env.get(var, "")
        if not val:
            result.error(f"[MISSING]  {var} is empty or absent")

    # ------------------------------------------------------------------
    # 2. Secret vars: presence, length, placeholder
    # ------------------------------------------------------------------
    for var, min_len, desc in SECRET_CHECKS:
        val = env.get(var, "")

        if not val:
            result.error(f"[MISSING]  {var} is empty or absent -- {desc}")
            continue

        if _normalise(val) in KNOWN_BAD_VALUES:
            result.error(f"[WEAK]     {var} contains a known placeholder value")

        if len(val) < min_len:
            result.error(f"[SHORT]    {var} must be >= {min_len} chars (got {len(val)})")

    # ------------------------------------------------------------------
    # 3. SECRET_KEY and JWT_SECRET_KEY must differ
    # ------------------------------------------------------------------
    sk = env.get("SECRET_KEY", "")
    jk = env.get("JWT_SECRET_KEY", "")
    if sk and jk and sk == jk:
        result.error("[DUPLICATE] SECRET_KEY and JWT_SECRET_KEY must be different")

    # ------------------------------------------------------------------
    # 4. DATABASE_URL must not contain default passwords
    # ------------------------------------------------------------------
    db_url = env.get("DATABASE_URL", "")
    if db_url:
        db_lower = db_url.lower()
        for bad in ("password", "123456", "admin123", "root", "change_me"):
            # Match as a password component (after ://user: and before @)
            match = re.search(r"://[^:]+:([^@]+)@", db_url)
            if match:
                pwd_in_url = match.group(1).lower()
                if bad in pwd_in_url:
                    result.error(f"[WEAK]     DATABASE_URL contains weak password component '{bad}'")
                    break
        # Also flag if it looks like a template
        if "change_me" in db_lower or "your_password" in db_lower:
            result.error("[WEAK]     DATABASE_URL appears to contain placeholder text")

    # ------------------------------------------------------------------
    # 5. ADMIN_PASSWORD must not be defaults
    # ------------------------------------------------------------------
    admin_pwd = env.get("ADMIN_PASSWORD", "")
    if admin_pwd and _normalise(admin_pwd) in ("admin123", "password", "admin", "root"):
        result.error("[WEAK]     ADMIN_PASSWORD is set to a default value")

    # ------------------------------------------------------------------
    # 6. FLASK_ENV should be 'production' in production files
    # ------------------------------------------------------------------
    flask_env = env.get("FLASK_ENV", "")
    if strict and flask_env and flask_env != "production":
        result.warn(f"[CONFIG]   FLASK_ENV is '{flask_env}', expected 'production'")

    # ------------------------------------------------------------------
    # 7. FERNET_KEY format check (should be base64)
    # ------------------------------------------------------------------
    fernet = env.get("FERNET_KEY", "")
    if fernet:
        import base64
        try:
            decoded = base64.urlsafe_b64decode(fernet)
            if len(decoded) != 32:
                result.error(f"[FORMAT]   FERNET_KEY decodes to {len(decoded)} bytes, expected 32")
        except Exception:
            result.error("[FORMAT]   FERNET_KEY is not valid base64")

    # ------------------------------------------------------------------
    # 8. Warn about empty optional vars
    # ------------------------------------------------------------------
    optional_warn = ["DEEPSEEK_API_KEY", "SENTRY_DSN"]
    for var in optional_warn:
        if not env.get(var, ""):
            result.warn(f"[OPTIONAL] {var} is empty -- some features may be disabled")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate production secrets for AI Accounting System."
    )
    parser.add_argument(
        "--env-file", metavar="PATH",
        help="Path to .env file to validate (default: .env.production in project root)",
    )
    parser.add_argument(
        "--from-env", action="store_true",
        help="Validate OS environment variables instead of a file",
    )
    parser.add_argument(
        "--strict", action="store_true", default=True,
        help="Enable strict mode (default: True)",
    )
    parser.add_argument(
        "--no-strict", dest="strict", action="store_false",
        help="Disable strict mode (allows non-production FLASK_ENV, etc.)",
    )

    args = parser.parse_args()

    env = _get_env(args.env_file, args.from_env)
    if not env:
        source = "OS environment" if args.from_env else (args.env_file or ".env.production")
        print(f"[ERROR] Could not load environment from: {source}")
        sys.exit(1)

    source_label = "OS environment" if args.from_env else (args.env_file or ".env.production")
    result = validate(env, strict=args.strict)

    # Print warnings
    for w in result.warnings:
        print(f"  WARN  {w}")

    if result.ok:
        print(f"[PASS] All secrets in {source_label} passed validation.")
        if result.warnings:
            print(f"       ({len(result.warnings)} warning(s))")
        sys.exit(0)
    else:
        print(f"[FAIL] {len(result.errors)} error(s) found in {source_label}:")
        for e in result.errors:
            print(f"  {e}")
        if result.warnings:
            print(f"  ({len(result.warnings)} warning(s))")
        sys.exit(1)


if __name__ == "__main__":
    main()
