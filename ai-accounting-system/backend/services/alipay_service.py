"""Alipay payment service wrapper."""

import hashlib
import hmac
import json
import time
import uuid
from urllib.parse import urlencode

from flask import current_app


def _get_config():
    """Get Alipay configuration from Flask app."""
    return {
        'app_id': current_app.config.get('ALIPAY_APP_ID', ''),
        'private_key': current_app.config.get('ALIPAY_PRIVATE_KEY', ''),
        'public_key': current_app.config.get('ALIPAY_PUBLIC_KEY', ''),
        'notify_url': current_app.config.get('ALIPAY_NOTIFY_URL', ''),
        'return_url': current_app.config.get('ALIPAY_RETURN_URL', ''),
    }


def create_trade(out_trade_no, total_amount, subject, body=''):
    """Create an Alipay trade and return the payment URL.

    This is a simplified implementation for demonstration.
    In production, use the official alipay-sdk-python library.
    """
    cfg = _get_config()

    if not cfg['app_id']:
        raise ValueError('Alipay app_id not configured')

    # Build common params
    params = {
        'app_id': cfg['app_id'],
        'method': 'alipay.trade.page.pay',
        'charset': 'utf-8',
        'sign_type': 'RSA2',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'version': '1.0',
        'notify_url': cfg['notify_url'],
        'return_url': cfg['return_url'],
        'biz_content': json.dumps({
            'out_trade_no': out_trade_no,
            'total_amount': str(total_amount),
            'subject': subject,
            'body': body,
            'product_code': 'FAST_INSTANT_TRADE_PAY',
        }, ensure_ascii=False)
    }

    # Sign the params
    params['sign'] = _sign_params(params, cfg['private_key'])

    # Build the payment URL
    gateway = 'https://openapi.alipay.com/gateway.do'
    payment_url = f'{gateway}?{urlencode(params)}'

    return {
        'payment_url': payment_url,
        'out_trade_no': out_trade_no,
    }


def verify_callback(params):
    """Verify Alipay async notification signature.

    This is a simplified implementation. In production, use the official SDK
    with proper RSA2 signature verification.
    """
    cfg = _get_config()

    sign = params.pop('sign', '')
    sign_type = params.pop('sign_type', 'RSA2')

    # Filter out empty values
    filtered = {k: v for k, v in params.items() if v is not None and v != ''}

    # Sort and join
    sorted_params = sorted(filtered.items())
    sign_str = '&'.join(f'{k}={v}' for k, v in sorted_params)

    # Verify signature (simplified - in production use proper RSA2 verification)
    # For now, we'll do a basic check
    if not cfg['public_key']:
        current_app.logger.warning('Alipay public key not configured, skipping signature verification')
        return True

    # TODO: Implement proper RSA2 signature verification
    # For development, return True
    return True


def query_trade(out_trade_no):
    """Query an Alipay trade status."""
    cfg = _get_config()

    params = {
        'app_id': cfg['app_id'],
        'method': 'alipay.trade.query',
        'charset': 'utf-8',
        'sign_type': 'RSA2',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'version': '1.0',
        'biz_content': json.dumps({
            'out_trade_no': out_trade_no,
        }, ensure_ascii=False)
    }

    params['sign'] = _sign_params(params, cfg['private_key'])

    # In production, make actual API call
    # For now, return a placeholder
    return {
        'trade_status': 'WAIT_BUYER_PAY',
        'out_trade_no': out_trade_no,
    }


def generate_out_trade_no():
    """Generate a unique trade number."""
    return f'AI{int(time.time())}{uuid.uuid4().hex[:8].upper()}'


def _sign_params(params, private_key):
    """Sign parameters with RSA2 (SHA256WithRSA).

    This is a simplified implementation. In production, use proper RSA signing.
    """
    # Filter out empty values and sign param
    filtered = {k: v for k, v in params.items()
                if v is not None and v != '' and k != 'sign'}

    # Sort and join
    sorted_params = sorted(filtered.items())
    sign_str = '&'.join(f'{k}={v}' for k, v in sorted_params)

    # For development, use HMAC as a placeholder
    # In production, use RSA2 signing with private_key
    if private_key:
        return hmac.new(
            private_key.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    return hashlib.sha256(sign_str.encode('utf-8')).hexdigest()
