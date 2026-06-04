import os
import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from extensions import db, limiter
from models.user import User
from models.refresh_token import RefreshToken
from models.login_history import LoginHistory
from models.password_reset_token import PasswordResetToken
from models.email_verification_token import EmailVerificationToken
from utils.jwt_helper import (
    create_tokens, token_required, verify_token,
    revoke_token_family, revoke_all_user_tokens, create_access_token
)
from utils.security import validate_password_strength, parse_user_agent
from utils.email_service import EmailService

logger = logging.getLogger(__name__)
biz_logger = logging.getLogger('business')

auth_bp = Blueprint('auth', __name__)


def _hash_token(token):
    """对 token 进行哈希处理后存储（防止数据库泄露时 token 被直接使用）"""
    return hashlib.sha256(token.encode()).hexdigest()


# ==================== 注册 ====================

@auth_bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """用户注册 - 需要邮箱验证"""
    data = request.get_json()

    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'error': '请填写所有必填字段'}), 400

    # 密码强度校验
    valid, msg = validate_password_strength(data['password'])
    if not valid:
        return jsonify({'error': msg}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': '用户名已存在'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': '邮箱已被注册'}), 400

    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])

    db.session.add(user)
    db.session.flush()  # Get user.id before creating tenant

    # Auto-create personal workspace tenant
    from services.tenant_service import create_tenant
    tenant, tenant_err = create_tenant(
        name=f"{data['username']}'s Workspace",
        owner_id=user.id,
        max_members=5,
    )
    if tenant:
        user.tenant_id = tenant.id

    db.session.commit()

    # 创建邮箱验证令牌
    _create_email_verification(user)

    biz_logger.info(f"New user registered: id={user.id} username={user.username} ip={request.remote_addr}")

    return jsonify({
        'message': '注册成功，请查收验证邮件',
        'user': user.to_dict()
    }), 201


def _create_email_verification(user):
    """为用户创建邮箱验证令牌并发送邮件"""
    token = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    # 删除旧的验证令牌
    EmailVerificationToken.query.filter_by(user_id=user.id).delete()

    evt = EmailVerificationToken(
        user_id=user.id,
        token=_hash_token(token),
        email=user.email,
        expires_at=expires_at
    )
    db.session.add(evt)
    db.session.commit()

    frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
    verify_link = f"{frontend_url}/verify-email?token={token}"
    EmailService.send_email_verification(user.email, verify_link)


# ==================== 登录 ====================

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """用户登录 - 带账号锁定和登录历史"""
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': '请填写用户名和密码'}), 400

    user = User.query.filter(
        (User.username == data['username']) | (User.email == data['username'])
    ).first()

    ua = request.headers.get('User-Agent', '')
    ip = request.remote_addr or ''
    device = parse_user_agent(ua)

    if not user:
        _record_login_history(None, ip, ua, device, False, 'user_not_found')
        return jsonify({'error': '用户名或密码错误'}), 401

    # 检查账号是否被锁定
    if user.is_locked():
        _record_login_history(user.id, ip, ua, device, False, 'account_locked')
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        return jsonify({'error': f'账号已被锁定，请在{remaining}分钟后重试'}), 403

    if not user.check_password(data['password']):
        user.record_failed_login(
            max_attempts=current_app.config.get('MAX_LOGIN_ATTEMPTS', 5),
            lockout_minutes=current_app.config.get('LOCKOUT_DURATION_MINUTES', 30)
        )
        _record_login_history(user.id, ip, ua, device, False, 'wrong_password')

        remaining_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5) - user.failed_login_attempts
        if remaining_attempts > 0:
            return jsonify({'error': f'用户名或密码错误，还剩{remaining_attempts}次尝试机会'}), 401
        else:
            return jsonify({'error': '密码错误次数过多，账号已被锁定30分钟'}), 403

    if not user.is_active:
        _record_login_history(user.id, ip, ua, device, False, 'account_disabled')
        return jsonify({'error': '账号已被禁用'}), 403

    # 登录成功 — 检查是否需要 2FA
    user.reset_failed_login()
    db.session.commit()

    # Ensure user has a tenant (auto-create workspace if needed)
    if not user.tenant_id:
        from services.tenant_service import create_tenant
        tenant, _ = create_tenant(f"{user.username}的工作区", user.id)
        if tenant:
            user.tenant_id = tenant.id
            db.session.commit()

    if user.totp_enabled:
        # 生成短期 2FA pending token (5分钟有效)
        import jwt as pyjwt
        temp_payload = {
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(minutes=5),
            'iat': datetime.utcnow(),
            'type': '2fa_pending'
        }
        temp_token = pyjwt.encode(
            temp_payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm='HS256'
        )
        _record_login_history(user.id, ip, ua, device, True, '2fa_pending')
        return jsonify({
            'requires_2fa': True,
            'temp_token': temp_token,
            'message': '请输入二步验证码'
        })

    tokens = create_tokens(
        user.id,
        device_info=ua,
        ip_address=ip,
        token_family=None
    )

    _record_login_history(user.id, ip, ua, device, True, '')
    _log_audit('user.login', user.id, 'user', user.id)
    biz_logger.info(f"User logged in: id={user.id} username={user.username} ip={ip}")

    return jsonify({
        'message': '登录成功',
        'user': user.to_dict(),
        'email_verified': user.email_verified,
        'current_tenant_id': user.tenant_id,
        **tokens
    })


@auth_bp.route('/login/verify-2fa', methods=['POST'])
@limiter.limit("10 per minute")
def verify_2fa_login():
    """Complete login with 2FA verification."""
    import jwt as pyjwt

    data = request.get_json()
    temp_token = data.get('temp_token', '')
    code = data.get('code', '')

    if not temp_token or not code:
        return jsonify({'error': '缺少必要参数'}), 400

    # Verify temp token
    try:
        payload = pyjwt.decode(
            temp_token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
    except pyjwt.ExpiredSignatureError:
        return jsonify({'error': '验证已过期，请重新登录'}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({'error': '无效的验证令牌'}), 401

    if payload.get('type') != '2fa_pending':
        return jsonify({'error': '令牌类型错误'}), 400

    user = User.query.get(payload['user_id'])
    if not user or not user.is_active:
        return jsonify({'error': '用户不存在或已被禁用'}), 401

    # Verify TOTP code
    from models.totp_secret import TotpSecret
    from security import totp as totp_service

    ts = TotpSecret.query.filter_by(user_id=user.id, is_enabled=True).first()
    if not ts:
        return jsonify({'error': '二步验证未配置'}), 400

    if not totp_service.verify_code(ts.secret, code):
        return jsonify({'error': '验证码错误'}), 400

    ts.last_used_at = datetime.utcnow()
    db.session.commit()

    # Ensure user has a tenant (auto-create workspace if needed)
    if not user.tenant_id:
        from services.tenant_service import create_tenant
        tenant, _ = create_tenant(f"{user.username}的工作区", user.id)
        if tenant:
            user.tenant_id = tenant.id
            db.session.commit()

    ua = request.headers.get('User-Agent', '')
    ip = request.remote_addr or ''

    tokens = create_tokens(
        user.id,
        device_info=ua,
        ip_address=ip,
        token_family=None
    )

    _record_login_history(user.id, ip, ua, {}, True, '')
    _log_audit('user.login_2fa', user.id, 'user', user.id)
    biz_logger.info(f"User logged in (2FA): id={user.id} username={user.username} ip={ip}")

    return jsonify({
        'message': '登录成功',
        'user': user.to_dict(),
        **tokens
    })


def _log_audit(action, user_id, resource_type=None, resource_id=None, details=None):
    """Write an audit log entry (best-effort)."""
    try:
        from security.audit import log_action
        log_action(action, user_id=user_id, resource_type=resource_type,
                   resource_id=resource_id, details=details)
    except Exception:
        pass


def _record_login_history(user_id, ip, ua, device, success, reason):
    """记录登录历史"""
    if not user_id:
        return
    entry = LoginHistory(
        user_id=user_id,
        ip_address=ip,
        user_agent=ua[:500],
        device_type=device.get('device_type', ''),
        browser=device.get('browser', ''),
        os=device.get('os', ''),
        success=success,
        failure_reason=reason
    )
    db.session.add(entry)
    db.session.commit()


# ==================== 登出 ====================

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout():
    """用户登出 - 撤销刷新令牌"""
    user = request.current_user
    data = request.get_json() or {}

    if data.get('revoke_all'):
        revoke_all_user_tokens(user.id)
        _log_audit('user.logout_all', user.id, 'user', user.id)
        biz_logger.info(f"User logged out all devices: user_id={user.id}")
        return jsonify({'message': '已退出所有设备'})

    # 撤销当前会话的令牌家族
    refresh_token_str = data.get('refresh_token')
    if refresh_token_str:
        payload = verify_token(refresh_token_str)
        if payload and payload.get('type') == 'refresh':
            family = payload.get('family', '')
            if family:
                revoke_token_family(family)
                biz_logger.info(f"User logged out: user_id={user.id} family={family}")
                return jsonify({'message': '已退出登录'})

    # 如果没有提供 refresh_token，至少撤销当前 access token 的 family
    family = getattr(request, 'token_family', '')
    if family:
        revoke_token_family(family)

    biz_logger.info(f"User logged out: user_id={user.id}")
    return jsonify({'message': '已退出登录'})


# ==================== 当前用户 ====================

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    """获取当前用户信息"""
    return jsonify({'user': request.current_user.to_dict()})


@auth_bp.route('/me', methods=['PUT'])
@token_required
def update_profile():
    """更新用户资料"""
    user = request.current_user
    data = request.get_json()

    if data.get('username'):
        existing = User.query.filter_by(username=data['username']).first()
        if existing and existing.id != user.id:
            return jsonify({'error': '用户名已存在'}), 400
        user.username = data['username']

    if data.get('email'):
        existing = User.query.filter_by(email=data['email']).first()
        if existing and existing.id != user.id:
            return jsonify({'error': '邮箱已被注册'}), 400
        user.email = data['email']

    if 'phone' in data:
        user.phone = data['phone'] or ''

    if 'avatar' in data:
        user.avatar = data['avatar'] or ''

    db.session.commit()
    biz_logger.info(f"Profile updated: user_id={user.id}")

    return jsonify({
        'message': '更新成功',
        'user': user.to_dict()
    })


# ==================== 修改密码 ====================

@auth_bp.route('/password', methods=['PUT'])
@token_required
@limiter.limit("5 per minute")
def change_password():
    """修改密码 - 修改后撤销所有令牌"""
    user = request.current_user
    data = request.get_json()

    if not data.get('old_password') or not data.get('new_password'):
        return jsonify({'error': '请填写旧密码和新密码'}), 400

    # 新密码强度校验
    valid, msg = validate_password_strength(data['new_password'])
    if not valid:
        return jsonify({'error': msg}), 400

    if not user.check_password(data['old_password']):
        biz_logger.warning(f"Wrong old password: user_id={user.id} ip={request.remote_addr}")
        return jsonify({'error': '旧密码错误'}), 400

    user.set_password(data['new_password'])
    db.session.commit()

    # 修改密码后撤销所有令牌，强制重新登录
    revoke_all_user_tokens(user.id)

    _log_audit('user.password_changed', user.id, 'user', user.id)
    biz_logger.info(f"Password changed: user_id={user.id}")
    return jsonify({'message': '密码修改成功，请重新登录'})


# ==================== 刷新令牌 ====================

@auth_bp.route('/refresh', methods=['POST'])
@limiter.limit("30 per minute")
def refresh_token():
    """刷新访问令牌 - 带令牌轮换和被盗检测"""
    data = request.get_json()
    token_str = data.get('refresh_token')

    if not token_str:
        return jsonify({'error': '缺少刷新令牌'}), 400

    payload = verify_token(token_str)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({'error': '无效的刷新令牌'}), 401

    jti = payload.get('jti')
    family = payload.get('family', '')
    user_id = payload['user_id']

    # 查找数据库中的刷新令牌记录
    rt = RefreshToken.query.filter_by(jti=jti).first()

    if not rt:
        # 令牌不在数据库中 - 可能是旧的无状态令牌，允许一次迁移
        user = User.query.get(user_id)
        if not user or not user.is_active:
            return jsonify({'error': '用户不存在或已被禁用'}), 401
        tokens = create_tokens(
            user.id,
            device_info=request.headers.get('User-Agent', ''),
            ip_address=request.remote_addr or ''
        )
        return jsonify({'message': '令牌刷新成功', **tokens})

    if rt.is_revoked:
        # 已撤销的令牌被重用 - 可能是被盗令牌，撤销整个家族
        revoke_token_family(rt.token_family)
        biz_logger.warning(
            f"Stolen refresh token detected! Revoked family={rt.token_family} "
            f"user_id={user_id} ip={request.remote_addr}"
        )
        return jsonify({'error': '令牌已被撤销，请重新登录'}), 401

    user = User.query.get(user_id)
    if not user or not user.is_active:
        return jsonify({'error': '用户不存在或已被禁用'}), 401

    # 撤销当前刷新令牌
    rt.is_revoked = True

    # 创建新的令牌对（同一 token_family）
    tokens = create_tokens(
        user.id,
        device_info=request.headers.get('User-Agent', ''),
        ip_address=request.remote_addr or '',
        token_family=rt.token_family
    )

    return jsonify({
        'message': '令牌刷新成功',
        **tokens
    })


# ==================== 忘记密码 / 重置密码 ====================

@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute")
def forgot_password():
    """发送密码重置邮件（始终返回成功，防止邮箱枚举）"""
    data = request.get_json()
    email = data.get('email', '').strip() if data else ''

    if not email:
        return jsonify({'error': '请输入邮箱地址'}), 400

    user = User.query.filter_by(email=email).first()

    # 始终返回成功，防止邮箱枚举攻击
    if user:
        # 删除旧的重置令牌
        PasswordResetToken.query.filter_by(user_id=user.id, used=False).delete()

        token = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        prt = PasswordResetToken(
            user_id=user.id,
            token=_hash_token(token),
            expires_at=expires_at
        )
        db.session.add(prt)
        db.session.commit()

        frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
        reset_link = f"{frontend_url}/reset-password?token={token}"
        EmailService.send_password_reset(user.email, reset_link)

        biz_logger.info(f"Password reset requested: user_id={user.id} ip={request.remote_addr}")

    return jsonify({'message': '如果该邮箱已注册，重置链接将发送到您的邮箱'})


@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit("5 per minute")
def reset_password():
    """使用令牌重置密码"""
    data = request.get_json()

    if not data or not data.get('token') or not data.get('new_password'):
        return jsonify({'error': '缺少必要参数'}), 400

    # 密码强度校验
    valid, msg = validate_password_strength(data['new_password'])
    if not valid:
        return jsonify({'error': msg}), 400

    token_hash = _hash_token(data['token'])
    prt = PasswordResetToken.query.filter_by(token=token_hash).first()

    if not prt:
        return jsonify({'error': '无效的重置令牌'}), 400

    if prt.used:
        return jsonify({'error': '该令牌已被使用'}), 400

    if prt.expires_at < datetime.utcnow():
        return jsonify({'error': '重置令牌已过期，请重新申请'}), 400

    user = User.query.get(prt.user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 400

    # 重置密码
    user.set_password(data['new_password'])
    prt.used = True
    db.session.commit()

    # 撤销所有令牌，强制重新登录
    revoke_all_user_tokens(user.id)

    biz_logger.info(f"Password reset completed: user_id={user.id} ip={request.remote_addr}")
    return jsonify({'message': '密码重置成功，请重新登录'})


# ==================== 邮箱验证 ====================

@auth_bp.route('/verify-email', methods=['GET'])
@limiter.limit("10 per minute")
def verify_email():
    """验证邮箱"""
    token = request.args.get('token', '').strip()
    if not token:
        return jsonify({'error': '缺少验证令牌'}), 400

    token_hash = _hash_token(token)
    evt = EmailVerificationToken.query.filter_by(token=token_hash).first()

    if not evt:
        return jsonify({'error': '无效的验证链接'}), 400

    if evt.expires_at < datetime.utcnow():
        return jsonify({'error': '验证链接已过期，请重新申请'}), 400

    user = User.query.get(evt.user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 400

    user.email_verified = True
    db.session.delete(evt)
    db.session.commit()

    biz_logger.info(f"Email verified: user_id={user.id}")
    return jsonify({'message': '邮箱验证成功', 'user': user.to_dict()})


@auth_bp.route('/resend-verification', methods=['POST'])
@token_required
@limiter.limit("3 per minute")
def resend_verification():
    """重新发送验证邮件"""
    user = request.current_user

    if user.email_verified:
        return jsonify({'message': '邮箱已验证，无需重复操作'})

    _create_email_verification(user)
    return jsonify({'message': '验证邮件已发送，请查收'})


# ==================== 会话管理 ====================

@auth_bp.route('/sessions', methods=['GET'])
@token_required
def get_sessions():
    """获取活跃会话列表"""
    user = request.current_user
    current_jti = getattr(request, 'token_jti', '')

    sessions = RefreshToken.query.filter_by(
        user_id=user.id,
        is_revoked=False
    ).filter(
        RefreshToken.expires_at > datetime.utcnow()
    ).order_by(RefreshToken.created_at.desc()).all()

    result = []
    for s in sessions:
        d = s.to_dict()
        d['is_current'] = (s.jti == current_jti)
        result.append(d)

    return jsonify({'sessions': result})


@auth_bp.route('/sessions/<int:session_id>', methods=['DELETE'])
@token_required
def revoke_session(session_id):
    """撤销指定会话"""
    user = request.current_user
    rt = RefreshToken.query.filter_by(id=session_id, user_id=user.id).first()

    if not rt:
        return jsonify({'error': '会话不存在'}), 404

    # 撤销该会话的整个令牌家族
    revoke_token_family(rt.token_family)

    biz_logger.info(f"Session revoked: user_id={user.id} session_id={session_id}")
    return jsonify({'message': '会话已撤销'})


# ==================== 登录历史 ====================

@auth_bp.route('/login-history', methods=['GET'])
@token_required
def get_login_history():
    """获取登录历史（分页）"""
    user = request.current_user
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 50)

    pagination = LoginHistory.query.filter_by(
        user_id=user.id
    ).order_by(
        LoginHistory.login_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'history': [entry.to_dict() for entry in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    })


# ==================== 头像上传 ====================

@auth_bp.route('/avatar', methods=['POST'])
@token_required
@limiter.limit("10 per minute")
def upload_avatar():
    """上传用户头像"""
    from services.storage import get_storage
    from services.image_service import ImageService

    user = request.current_user

    if 'image' not in request.files:
        return jsonify({'error': '请选择图片文件'}), 400

    file = request.files['image']
    if not file or not file.filename:
        return jsonify({'error': '请选择图片文件'}), 400

    # 验证文件类型
    allowed = {'png', 'jpg', 'jpeg', 'webp'}
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in allowed:
        return jsonify({'error': '不支持的图片格式，请使用 JPG/PNG/WEBP'}), 400

    # 验证文件大小
    max_size = current_app.config.get('AVATAR_MAX_SIZE_MB', 2) * 1024 * 1024
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)

    if file_size > max_size:
        return jsonify({'error': f'图片大小不能超过 {current_app.config.get("AVATAR_MAX_SIZE_MB", 2)}MB'}), 400

    if file_size == 0:
        return jsonify({'error': '图片文件为空'}), 400

    # 读取文件数据
    file_data = file.read()

    # 压缩图片
    quality = current_app.config.get('STORAGE_COMPRESS_QUALITY', 85)
    compressed = ImageService.compress(file_data, quality=quality)

    # 生成缩略图
    thumbnail_sizes = current_app.config.get('STORAGE_THUMBNAIL_SIZES', [150, 300])
    thumbnails = ImageService.generate_thumbnail(file_data, sizes=thumbnail_sizes)

    storage = get_storage()

    # 删除旧头像及缩略图
    if user.avatar and not user.avatar.startswith('/uploads/'):
        storage.delete(user.avatar)
        for size in thumbnail_sizes:
            thumb_key = _thumbnail_key(user.avatar, size)
            storage.delete(thumb_key)
    elif user.avatar:
        # Backward compat: old local path
        old_path = os.path.join(current_app.root_path, user.avatar.lstrip('/'))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    # 上传新头像
    filename = f"avatar_{user.id}_{uuid.uuid4().hex[:8]}.jpg"
    key = f"avatars/{filename}"
    storage.upload(compressed, key, content_type='image/jpeg')

    # 上传缩略图
    for size, thumb_data in thumbnails.items():
        thumb_key = _thumbnail_key(key, size)
        storage.upload(thumb_data, thumb_key, content_type='image/jpeg')

    user.avatar = key
    db.session.commit()

    biz_logger.info(f"Avatar uploaded: user_id={user.id}")
    return jsonify({
        'message': '头像上传成功',
        'user': user.to_dict()
    })


def _thumbnail_key(key: str, size: int) -> str:
    """Generate thumbnail key from original key: avatars/foo.jpg -> avatars/foo_thumb_150.jpg"""
    name, ext = key.rsplit('.', 1)
    return f"{name}_thumb_{size}.{ext}"


@auth_bp.route('/avatar', methods=['DELETE'])
@token_required
def delete_avatar():
    """删除用户头像"""
    from services.storage import get_storage

    user = request.current_user
    storage = get_storage()

    if user.avatar:
        if user.avatar.startswith('/uploads/'):
            # Backward compat: old local path
            old_path = os.path.join(current_app.root_path, user.avatar.lstrip('/'))
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass
        else:
            storage.delete(user.avatar)
            # Delete thumbnails
            thumbnail_sizes = current_app.config.get('STORAGE_THUMBNAIL_SIZES', [150, 300])
            for size in thumbnail_sizes:
                storage.delete(_thumbnail_key(user.avatar, size))

    user.avatar = ''
    db.session.commit()

    biz_logger.info(f"Avatar deleted: user_id={user.id}")
    return jsonify({
        'message': '头像已删除',
        'user': user.to_dict()
    })
