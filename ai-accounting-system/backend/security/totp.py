"""TOTP (Time-based One-Time Password) service for 2FA."""

import hashlib
import secrets
import logging

logger = logging.getLogger(__name__)

try:
    import pyotp
    import qrcode
    import io
    import base64
    HAS_TOTP = True
except ImportError:
    HAS_TOTP = False
    logger.warning("pyotp/qrcode not installed, 2FA will be unavailable")


def is_available():
    """Check if TOTP is available."""
    return HAS_TOTP


def generate_secret():
    """Generate a new TOTP secret."""
    if not HAS_TOTP:
        raise RuntimeError('pyotp not installed')
    return pyotp.random_base32()


def get_provisioning_uri(secret, email, issuer='AI Accounting'):
    """Get the provisioning URI for QR code generation."""
    if not HAS_TOTP:
        raise RuntimeError('pyotp not installed')
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def generate_qr_base64(secret, email, issuer='AI Accounting'):
    """Generate QR code as base64 PNG string."""
    if not HAS_TOTP:
        raise RuntimeError('pyotp/qrcode not installed')

    uri = get_provisioning_uri(secret, email, issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def verify_code(secret, code):
    """Verify a TOTP code."""
    if not HAS_TOTP:
        raise RuntimeError('pyotp not installed')

    if not code or len(code) != 6 or not code.isdigit():
        return False

    totp = pyotp.TOTP(secret)
    # Allow 1 time step tolerance (30 seconds each direction)
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count=8):
    """Generate backup codes for 2FA recovery."""
    codes = []
    for _ in range(count):
        code = secrets.token_hex(4).upper()  # 8 char hex code
        codes.append(f'{code[:4]}-{code[4:]}')
    return codes


def hash_backup_code(code):
    """Hash a backup code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def verify_backup_code(hashed_codes, code):
    """Verify a backup code against stored hashes.

    Returns (is_valid, remaining_codes).
    """
    if not hashed_codes or not code:
        return False, hashed_codes

    code_hash = hash_backup_code(code.strip().upper())
    remaining = [h for h in hashed_codes if h != code_hash]

    if len(remaining) < len(hashed_codes):
        return True, remaining

    return False, hashed_codes
