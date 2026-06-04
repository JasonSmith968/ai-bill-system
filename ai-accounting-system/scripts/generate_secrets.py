#!/usr/bin/env python3
"""
Generate all production secrets for AI Accounting System.

Usage:
    python scripts/generate_secrets.py              # Generate full .env.production
    python scripts/generate_secrets.py --force       # Overwrite existing file
    python scripts/generate_secrets.py --rotate SECRET_KEY  # Rotate one key
    python scripts/generate_secrets.py --validate    # Validate existing file

Only uses Python standard library (secrets, string, re, argparse, pathlib).
"""

import argparse
import os
import re
import secrets
import string
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Secret definitions: (env_var, generator_func_name, description)
# ---------------------------------------------------------------------------
SECRETS_SPEC = [
    ("SECRET_KEY",              "_gen_hex_64",   "Flask session signing key"),
    ("JWT_SECRET_KEY",          "_gen_hex_64",   "JWT token signing key"),
    ("FERNET_KEY",              "_gen_fernet",   "Symmetric encryption key (Fernet)"),
    ("MYSQL_ROOT_PASSWORD",     "_gen_alnum_32", "MySQL root password"),
    ("MYSQL_PASSWORD",          "_gen_alnum_32", "MySQL application password"),
    ("REDIS_PASSWORD",          "_gen_alnum_32", "Redis password"),
    ("ADMIN_PASSWORD",          "_gen_mixed_24", "Admin user password (mixed case + digits)"),
    ("MYSQL_EXPORTER_PASSWORD", "_gen_mixed_24", "MySQL exporter password"),
    ("GRAFANA_PASSWORD",        "_gen_mixed_24", "Grafana admin password"),
    ("METRICS_AUTH_TOKEN",      "_gen_hex_64",   "Prometheus /metrics bearer token"),
    ("REQUEST_SIGNING_SECRET",  "_gen_hex_64",   "Request HMAC signing secret"),
]

# Non-secret vars that are always written with defaults
STATIC_VARS = {
    "FLASK_ENV":              "production",
    "MYSQL_DATABASE":         "ai_accounting",
    "MYSQL_USER":             "ai_user",
    "DEEPSEEK_API_KEY":       "",
    "DEEPSEEK_API_URL":       "https://api.deepseek.com/v1/chat/completions",
    "CORS_ORIGINS":           "https://your-domain.com",
    "FRONTEND_URL":           "https://your-domain.com",
    "STORAGE_PROVIDER":       "local",
    "LOG_LEVEL":              "INFO",
    "SENTRY_DSN":             "",
    "GRAFANA_USER":           "admin",
    "RATELIMIT_STORAGE_URI":  "redis://redis:6379",
    "DATABASE_URL":           "mysql+pymysql://ai_user:<MYSQL_PASSWORD>@db:3306/ai_accounting",
    "REDIS_URL":              "redis://:<REDIS_PASSWORD>@redis:6379/0",
}

# ---------------------------------------------------------------------------
# Generator helpers (standard library only)
# ---------------------------------------------------------------------------

def _gen_hex_64() -> str:
    """64 hex characters."""
    return secrets.token_hex(32)


def _gen_alnum_32() -> str:
    """32 alphanumeric characters."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def _gen_mixed_24() -> str:
    """24 alphanumeric characters guaranteed to include upper, lower, and digit."""
    while True:
        pwd = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        if (any(c.isupper() for c in pwd)
                and any(c.islower() for c in pwd)
                and any(c.isdigit() for c in pwd)):
            return pwd


def _gen_fernet() -> str:
    """Generate a Fernet-compatible base64 key.

    We import cryptography lazily so the script still works when the
    package is absent (the user can install it if needed).
    """
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()
    except ImportError:
        # Fallback: manually build a url-safe base64 32-byte key
        import base64
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


# Map generator function names to callables
_GENERATORS = {
    "_gen_hex_64":   _gen_hex_64,
    "_gen_alnum_32": _gen_alnum_32,
    "_gen_mixed_24": _gen_mixed_24,
    "_gen_fernet":   _gen_fernet,
}

# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    """Return the project root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def _env_path() -> Path:
    return _project_root() / ".env.production"


def _read_existing_env(path: Path) -> dict[str, str]:
    """Parse an existing .env file into a dict (preserves comments/order)."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def _write_env(path: Path, secrets_map: dict[str, str], static: dict[str, str]) -> None:
    """Write a well-structured .env.production file."""
    lines: list[str] = [
        "# ==========================================================================",
        "# AI Accounting System -- Production Environment Variables",
        "# ==========================================================================",
        "# Generated by scripts/generate_secrets.py",
        f"# Date: {_now_iso()}",
        "# NEVER commit this file to version control.",
        "# ==========================================================================",
        "",
    ]

    # Group: Flask / Security
    lines += [
        "# --- Flask / Security ---",
        "FLASK_ENV=production",
        _kv("SECRET_KEY", secrets_map),
        _kv("JWT_SECRET_KEY", secrets_map),
        _kv("FERNET_KEY", secrets_map),
        "",
    ]

    # Group: Database
    db_password = secrets_map.get("MYSQL_PASSWORD", "<FILL_IN>")
    lines += [
        "# --- MySQL ---",
        "MYSQL_DATABASE=ai_accounting",
        "MYSQL_USER=ai_user",
        _kv("MYSQL_ROOT_PASSWORD", secrets_map),
        _kv("MYSQL_PASSWORD", secrets_map),
        f"DATABASE_URL=mysql+pymysql://ai_user:{db_password}@db:3306/ai_accounting",
        "",
    ]

    # Group: Redis
    redis_password = secrets_map.get("REDIS_PASSWORD", "<FILL_IN>")
    lines += [
        "# --- Redis ---",
        _kv("REDIS_PASSWORD", secrets_map),
        f"REDIS_URL=redis://:{redis_password}@redis:6379/0",
        "RATELIMIT_STORAGE_URI=redis://redis:6379",
        "",
    ]

    # Group: AI / LLM
    lines += [
        "# --- AI / LLM ---",
        "DEEPSEEK_API_KEY=",
        "DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions",
        "",
    ]

    # Group: Monitoring
    lines += [
        "# --- Monitoring ---",
        _kv("MYSQL_EXPORTER_PASSWORD", secrets_map),
        _kv("METRICS_AUTH_TOKEN", secrets_map),
        _kv("REQUEST_SIGNING_SECRET", secrets_map),
        "",
    ]

    # Group: Grafana
    lines += [
        "# --- Grafana ---",
        "GRAFANA_USER=admin",
        _kv("GRAFANA_PASSWORD", secrets_map),
        "",
    ]

    # Group: Admin
    lines += [
        "# --- Admin ---",
        _kv("ADMIN_PASSWORD", secrets_map),
        "",
    ]

    # Group: Application
    lines += [
        "# --- Application ---",
        "CORS_ORIGINS=https://your-domain.com",
        "FRONTEND_URL=https://your-domain.com",
        "STORAGE_PROVIDER=local",
        "LOG_LEVEL=INFO",
        "SENTRY_DSN=",
        "",
    ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _kv(key: str, sm: dict[str, str]) -> str:
    return f"{key}={sm.get(key, '')}"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Validation (subset -- full validation lives in validate_secrets.py)
# ---------------------------------------------------------------------------

KNOWN_BAD_VALUES = {
    "change_me", "changeme", "password", "123456", "admin123",
    "secret", "test", "default", "example", "your-secret-key",
    "change_me_generate_with_python_-c_secrets_token_hex_32",
    "sk-change_me_rotate_after_compromise",
    "exporter_password",
}

REQUIRED_VARS = [spec[0] for spec in SECRETS_SPEC] + [
    "DATABASE_URL", "REDIS_URL",
]


def validate_env(env: dict[str, str], *, strict: bool = True) -> list[str]:
    """Return a list of error strings. Empty = valid."""
    errors: list[str] = []

    for var in REQUIRED_VARS:
        val = env.get(var, "")
        if not val:
            errors.append(f"[MISSING] {var} is empty or absent")
            continue
        if val.lower().replace("_", "").replace("-", "") in KNOWN_BAD_VALUES:
            errors.append(f"[WEAK]    {var} contains a known placeholder value")

    # Length checks (hex secrets must be >= 32 chars = 64 hex chars for hex_64)
    hex_keys = {"SECRET_KEY", "JWT_SECRET_KEY", "METRICS_AUTH_TOKEN", "REQUEST_SIGNING_SECRET"}
    for k in hex_keys:
        val = env.get(k, "")
        if val and len(val) < 32:
            errors.append(f"[SHORT]   {k} must be >= 32 chars (got {len(val)})")

    alnum_keys = {"MYSQL_ROOT_PASSWORD", "MYSQL_PASSWORD", "REDIS_PASSWORD",
                  "ADMIN_PASSWORD", "MYSQL_EXPORTER_PASSWORD", "GRAFANA_PASSWORD"}
    for k in alnum_keys:
        val = env.get(k, "")
        if val and len(val) < 24:
            errors.append(f"[SHORT]   {k} must be >= 24 chars (got {len(val)})")

    # SECRET_KEY and JWT_SECRET_KEY must differ
    sk = env.get("SECRET_KEY", "")
    jk = env.get("JWT_SECRET_KEY", "")
    if sk and jk and sk == jk:
        errors.append("[DUPLICATE] SECRET_KEY and JWT_SECRET_KEY must be different")

    # DATABASE_URL must not contain default passwords
    db_url = env.get("DATABASE_URL", "")
    if db_url:
        for bad in ("password", "123456", "admin123"):
            if bad in db_url.lower():
                errors.append(f"[WEAK]    DATABASE_URL contains weak password '{bad}'")

    # ADMIN_PASSWORD must not be defaults
    admin_pwd = env.get("ADMIN_PASSWORD", "")
    if admin_pwd and admin_pwd.lower() in ("admin123", "password", "admin"):
        errors.append("[WEAK]    ADMIN_PASSWORD is a default value")

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_generate(args: argparse.Namespace) -> None:
    path = _env_path()

    if path.exists() and not args.force:
        print(f"[ERROR] {path} already exists. Use --force to overwrite.")
        sys.exit(1)

    secrets_map: dict[str, str] = {}
    for var, gen_name, _desc in SECRETS_SPEC:
        secrets_map[var] = _GENERATORS[gen_name]()

    _write_env(path, secrets_map, STATIC_VARS)

    print(f"[OK] Generated {path}")
    print()
    print("Secrets summary:")
    print("-" * 60)
    for var, _gen, desc in SECRETS_SPEC:
        val = secrets_map[var]
        masked = val[:6] + "..." + val[-4:] if len(val) > 12 else "(short)"
        print(f"  {var:30s}  {masked:20s}  # {desc}")
    print("-" * 60)
    print()
    print("Next steps:")
    print("  1. Review .env.production and adjust DATABASE_URL host/port if needed")
    print("  2. Set DEEPSEEK_API_KEY if using AI features")
    print("  3. Update CORS_ORIGINS and FRONTEND_URL for your domain")
    print("  4. Run: python scripts/validate_secrets.py")


def cmd_rotate(args: argparse.Namespace) -> None:
    path = _env_path()
    if not path.exists():
        print(f"[ERROR] {path} not found. Run without --rotate first.")
        sys.exit(1)

    target = args.rotate.upper()

    # Find spec
    spec = None
    for var, gen_name, desc in SECRETS_SPEC:
        if var == target:
            spec = (var, gen_name, desc)
            break

    if spec is None:
        print(f"[ERROR] Unknown secret: {target}")
        print(f"  Valid secrets: {', '.join(s[0] for s in SECRETS_SPEC)}")
        sys.exit(1)

    var, gen_name, desc = spec
    new_value = _GENERATORS[gen_name]()

    # Read, replace, write
    content = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^({re.escape(var)}=).*$", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(rf"\g<1>{new_value}", content)
    else:
        # Append if missing
        content += f"\n{var}={new_value}\n"

    # Also update derived vars
    if var == "MYSQL_PASSWORD":
        content = _update_derived_url(content, "DATABASE_URL", "ai_user", new_value, "db", "3306", "ai_accounting")
    elif var == "REDIS_PASSWORD":
        content = _update_derived_url(content, "REDIS_URL", None, new_value, "redis", "6379", "0")

    path.write_text(content, encoding="utf-8")

    masked = new_value[:6] + "..." + new_value[-4:] if len(new_value) > 12 else "(short)"
    print(f"[OK] Rotated {var} -> {masked}")
    print(f"     {desc}")
    print()
    print("IMPORTANT: Restart all services that consume this secret.")
    if var == "MYSQL_PASSWORD":
        print("           Also update MySQL user password to match.")
    elif var == "REDIS_PASSWORD":
        print("           Also update Redis requirepass to match.")


def _update_derived_url(content: str, url_var: str, user: str | None,
                         password: str, host: str, port: str, db: str) -> str:
    if user:
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
    else:
        url = f"redis://:{password}@{host}:{port}/{db}"
    pattern = re.compile(rf"^({re.escape(url_var)}=).*$", re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(rf"\g<1>{url}", content)
    return content + f"\n{url_var}={url}\n"


def cmd_validate(args: argparse.Namespace) -> None:
    path = _env_path()
    if not path.exists():
        print(f"[ERROR] {path} not found.")
        sys.exit(1)

    env = _read_existing_env(path)
    errors = validate_env(env)

    if errors:
        print(f"[FAIL] {len(errors)} issue(s) found in {path}:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"[PASS] All secrets in {path} look valid.")
        sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and manage production secrets for AI Accounting System."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing .env.production",
    )
    parser.add_argument(
        "--rotate", metavar="VAR_NAME",
        help="Rotate a single secret (e.g. --rotate SECRET_KEY)",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate existing .env.production",
    )

    args = parser.parse_args()

    if args.validate:
        cmd_validate(args)
    elif args.rotate:
        cmd_rotate(args)
    else:
        cmd_generate(args)


if __name__ == "__main__":
    main()
