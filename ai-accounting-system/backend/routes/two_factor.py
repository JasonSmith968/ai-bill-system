"""Two-Factor Authentication (TOTP) endpoints."""

import logging
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models.user import User
from models.totp_secret import TotpSecret
from utils.jwt_helper import token_required
from security import totp as totp_service
from security.audit import log_action

logger = logging.getLogger(__name__)

two_factor_bp = Blueprint('two_factor', __name__)


@two_factor_bp.route('/setup', methods=['POST'])
@token_required
def setup():
    """Generate a new TOTP secret and QR code for 2FA setup."""
    if not totp_service.is_available():
        return jsonify({'error': '二步验证功能暂不可用'}), 503

    user = request.current_user

    if user.totp_enabled:
        return jsonify({'error': '二步验证已启用，请先禁用后再重新设置'}), 400

    secret = totp_service.generate_secret()
    issuer = current_app.config.get('TOTP_ISSUER', 'AI Accounting')
    qr_base64 = totp_service.generate_qr_base64(secret, user.email, issuer)

    # Store secret temporarily (not yet enabled)
    existing = TotpSecret.query.filter_by(user_id=user.id).first()
    if existing:
        existing.secret = secret
        existing.is_enabled = False
    else:
        ts = TotpSecret(user_id=user.id, secret=secret, is_enabled=False)
        db.session.add(ts)
    db.session.commit()

    return jsonify({
        'secret': secret,
        'qr_code': f'data:image/png;base64,{qr_base64}'
    })


@two_factor_bp.route('/verify', methods=['POST'])
@token_required
def verify_setup():
    """Verify a TOTP code and enable 2FA."""
    if not totp_service.is_available():
        return jsonify({'error': '二步验证功能暂不可用'}), 503

    user = request.current_user
    data = request.get_json()
    code = data.get('code', '')

    if not code:
        return jsonify({'error': '请输入验证码'}), 400

    ts = TotpSecret.query.filter_by(user_id=user.id).first()
    if not ts:
        return jsonify({'error': '请先初始化二步验证'}), 400

    if not totp_service.verify_code(ts.secret, code):
        return jsonify({'error': '验证码错误'}), 400

    # Enable 2FA
    ts.is_enabled = True
    user.totp_enabled = True

    # Generate backup codes
    backup_codes = totp_service.generate_backup_codes()
    ts.set_backup_codes(backup_codes)

    db.session.commit()

    log_action('user.2fa_enabled', user_id=user.id, resource_type='user', resource_id=user.id)

    return jsonify({
        'message': '二步验证已启用',
        'backup_codes': backup_codes
    })


@two_factor_bp.route('/disable', methods=['POST'])
@token_required
def disable():
    """Disable 2FA (requires current TOTP code)."""
    user = request.current_user
    data = request.get_json()
    code = data.get('code', '')

    if not user.totp_enabled:
        return jsonify({'error': '二步验证未启用'}), 400

    if not code:
        return jsonify({'error': '请输入验证码'}), 400

    ts = TotpSecret.query.filter_by(user_id=user.id).first()
    if not ts:
        return jsonify({'error': '二步验证配置异常'}), 400

    if not totp_service.verify_code(ts.secret, code):
        return jsonify({'error': '验证码错误'}), 400

    ts.is_enabled = False
    user.totp_enabled = False
    db.session.commit()

    log_action('user.2fa_disabled', user_id=user.id, resource_type='user', resource_id=user.id)

    return jsonify({'message': '二步验证已禁用'})


@two_factor_bp.route('/backup-codes', methods=['GET'])
@token_required
def get_backup_codes():
    """Regenerate backup codes (requires current TOTP code)."""
    user = request.current_user

    if not user.totp_enabled:
        return jsonify({'error': '二步验证未启用'}), 400

    ts = TotpSecret.query.filter_by(user_id=user.id).first()
    if not ts:
        return jsonify({'error': '二步验证配置异常'}), 400

    # Generate new backup codes
    backup_codes = totp_service.generate_backup_codes()
    ts.set_backup_codes(backup_codes)
    db.session.commit()

    log_action('user.backup_codes_regenerated', user_id=user.id, resource_type='user', resource_id=user.id)

    return jsonify({'backup_codes': backup_codes})


@two_factor_bp.route('/backup-verify', methods=['POST'])
def backup_verify():
    """Verify using a backup code (used during login when TOTP device is unavailable)."""
    data = request.get_json()
    user_id = data.get('user_id')
    code = data.get('code', '')

    if not user_id or not code:
        return jsonify({'error': '缺少必要参数'}), 400

    ts = TotpSecret.query.filter_by(user_id=user_id, is_enabled=True).first()
    if not ts:
        return jsonify({'error': '二步验证未启用'}), 400

    backup_codes = ts.get_backup_codes()
    is_valid, remaining = totp_service.verify_backup_code(backup_codes, code)

    if not is_valid:
        return jsonify({'error': '备用码错误'}), 400

    # Update remaining backup codes
    ts.set_backup_codes(remaining)
    ts.last_used_at = db.func.now()
    db.session.commit()

    log_action('user.backup_code_used', user_id=user_id, resource_type='user', resource_id=user_id)

    return jsonify({
        'message': '验证成功',
        'remaining_codes': len(remaining)
    })
