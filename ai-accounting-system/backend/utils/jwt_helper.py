import jwt
import uuid
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app

from models.user import User

logger = logging.getLogger(__name__)


def create_tokens(user_id, device_info='', ip_address='', token_family=None):
    """创建访问令牌和刷新令牌（带 jti 和 token_family）"""
    from models.refresh_token import RefreshToken
    from extensions import db

    jti = str(uuid.uuid4())
    if not token_family:
        token_family = str(uuid.uuid4())

    # 获取用户角色和权限
    from models.user import User
    user = User.query.get(user_id)
    role_name = user.role_name if user else 'member'
    permissions = user.get_permission_codenames() if user else []

    # Get tenant context
    tenant_id = getattr(user, 'tenant_id', None) if user else None
    if not tenant_id and user:
        from models.tenant import TenantMember
        m = TenantMember.query.filter_by(user_id=user.id).first()
        if m:
            tenant_id = m.tenant_id
    tenant_role = user.get_tenant_role(tenant_id) if user and tenant_id else None

    # 访问令牌
    access_exp = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(minutes=15))
    access_payload = {
        'user_id': user_id,
        'tenant_id': tenant_id,
        'tenant_role': tenant_role,
        'exp': datetime.utcnow() + access_exp,
        'iat': datetime.utcnow(),
        'type': 'access',
        'jti': jti,
        'family': token_family,
        'role': role_name,
        'permissions': permissions
    }
    access_token = jwt.encode(
        access_payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

    # 刷新令牌
    refresh_jti = str(uuid.uuid4())
    refresh_exp = current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', timedelta(days=30))
    refresh_payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + refresh_exp,
        'iat': datetime.utcnow(),
        'type': 'refresh',
        'jti': refresh_jti,
        'family': token_family
    }
    refresh_token = jwt.encode(
        refresh_payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

    # 存储刷新令牌到数据库
    rt = RefreshToken(
        user_id=user_id,
        jti=refresh_jti,
        token_family=token_family,
        device_info=device_info[:256] if device_info else '',
        ip_address=ip_address or '',
        expires_at=datetime.utcnow() + refresh_exp
    )
    db.session.add(rt)
    db.session.commit()

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer'
    }


def create_access_token(user_id, token_family='', jti=None):
    """仅创建访问令牌（用于刷新流程）"""
    new_jti = str(uuid.uuid4())

    # 获取用户角色和权限
    from models.user import User
    user = User.query.get(user_id)
    role_name = user.role_name if user else 'member'
    permissions = user.get_permission_codenames() if user else []

    # Get tenant context
    tenant_id = getattr(user, 'tenant_id', None) if user else None
    if not tenant_id and user:
        from models.tenant import TenantMember
        m = TenantMember.query.filter_by(user_id=user.id).first()
        if m:
            tenant_id = m.tenant_id
    tenant_role = user.get_tenant_role(tenant_id) if user and tenant_id else None

    access_exp = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(minutes=15))
    access_payload = {
        'user_id': user_id,
        'tenant_id': tenant_id,
        'tenant_role': tenant_role,
        'exp': datetime.utcnow() + access_exp,
        'iat': datetime.utcnow(),
        'type': 'access',
        'jti': new_jti,
        'family': token_family,
        'role': role_name,
        'permissions': permissions
    }
    return jwt.encode(
        access_payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )


def verify_token(token):
    """验证令牌"""
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def revoke_token_family(token_family):
    """撤销整个令牌家族（检测到令牌被盗用时）"""
    from models.refresh_token import RefreshToken
    from extensions import db

    tokens = RefreshToken.query.filter_by(
        token_family=token_family,
        is_revoked=False
    ).all()
    for t in tokens:
        t.is_revoked = True
    db.session.commit()
    logger.warning(f"Revoked token family: {token_family} ({len(tokens)} tokens)")


def revoke_all_user_tokens(user_id):
    """撤销用户所有刷新令牌"""
    from models.refresh_token import RefreshToken
    from extensions import db

    tokens = RefreshToken.query.filter_by(
        user_id=user_id,
        is_revoked=False
    ).all()
    for t in tokens:
        t.is_revoked = True
    db.session.commit()
    logger.info(f"Revoked all tokens for user {user_id} ({len(tokens)} tokens)")


def token_required(f):
    """令牌验证装饰器 - 仅接受 access 类型令牌"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 从请求头获取令牌
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]

        if not token:
            return jsonify({'error': '缺少认证令牌'}), 401

        # 验证令牌
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': '令牌无效或已过期'}), 401

        # 安全校验：仅允许 access 类型令牌
        if payload.get('type') != 'access':
            return jsonify({'error': '令牌类型错误'}), 401

        # 获取用户
        user = User.query.get(payload['user_id'])
        if not user or not user.is_active:
            return jsonify({'error': '用户不存在或已被禁用'}), 401

        # 将用户信息添加到请求上下文
        request.current_user = user
        request.token_jti = payload.get('jti')
        request.token_family = payload.get('family')
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if not request.current_user.is_admin:
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)

    return decorated
