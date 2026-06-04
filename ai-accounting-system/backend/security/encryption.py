"""Fernet-based encryption for sensitive data."""

import logging
from flask import current_app

logger = logging.getLogger(__name__)

_fernet = None


def _get_fernet():
    """Get or create Fernet instance from config."""
    global _fernet
    if _fernet is not None:
        return _fernet

    try:
        from cryptography.fernet import Fernet
        key = current_app.config.get('FERNET_KEY', '')
        if not key:
            logger.warning('FERNET_KEY not configured, encryption unavailable')
            return None
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet
    except Exception as e:
        logger.error(f'Failed to initialize Fernet: {e}')
        return None


def encrypt_value(plaintext):
    """Encrypt a string value. Returns ciphertext string."""
    if not plaintext:
        return ''
    f = _get_fernet()
    if not f:
        logger.warning('Encryption unavailable, returning plaintext')
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext):
    """Decrypt a ciphertext string. Returns plaintext."""
    if not ciphertext:
        return ''
    f = _get_fernet()
    if not f:
        logger.warning('Decryption unavailable, returning ciphertext')
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.error(f'Decryption failed: {e}')
        return ''


def mask_payment_data(value):
    """Mask sensitive payment data (card numbers, etc.)."""
    if not value or len(value) < 8:
        return '****'
    return f'{value[:4]}****{value[-4:]}'


def mask_email(email):
    """Mask email address."""
    if not email or '@' not in email:
        return '***'
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked_local = local[0] + '***'
    else:
        masked_local = local[0] + '***' + local[-1]
    return f'{masked_local}@{domain}'
