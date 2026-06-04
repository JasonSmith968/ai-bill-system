"""Tenant management API — CRUD, member management, switching."""

import logging
from flask import Blueprint, request, jsonify, g
from extensions import db, limiter
from utils.jwt_helper import token_required
from middleware.tenant_context import require_tenant, require_tenant_role
from services import tenant_service

logger = logging.getLogger(__name__)
biz_logger = logging.getLogger('business')

tenant_bp = Blueprint('tenant', __name__)


# ==================== List / Create ====================

@tenant_bp.route('', methods=['GET'])
@token_required
def list_tenants():
    """List all tenants the current user belongs to."""
    user = request.current_user
    tenants = tenant_service.get_user_tenants(user.id)
    result = []
    for t in tenants:
        d = t.to_dict()
        d['role'] = user.get_tenant_role(t.id)
        d['is_current'] = (t.id == user.tenant_id)
        result.append(d)
    return jsonify({'tenants': result})


@tenant_bp.route('', methods=['POST'])
@token_required
@limiter.limit("5 per hour")
def create_tenant():
    """Create a new tenant (organization/workspace)."""
    user = request.current_user
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({'error': '请填写租户名称'}), 400

    name = data['name'].strip()
    if len(name) < 2 or len(name) > 100:
        return jsonify({'error': '名称长度需在 2-100 之间'}), 400

    max_members = data.get('max_members', 5)

    tenant, error = tenant_service.create_tenant(
        name=name,
        owner_id=user.id,
        max_members=max_members,
    )

    if error:
        return jsonify({'error': error}), 400

    biz_logger.info(f"Tenant created: id={tenant.id} name={name} by user={user.id}")
    return jsonify({
        'message': '租户创建成功',
        'tenant': tenant.to_dict(),
    }), 201


# ==================== Current Tenant ====================

@tenant_bp.route('/current', methods=['GET'])
@token_required
@require_tenant
def get_current_tenant():
    """Get current tenant details."""
    tenant = g.current_tenant
    d = tenant.to_dict()
    d['role'] = getattr(g, 'tenant_role', None)
    return jsonify({'tenant': d})


@tenant_bp.route('/<int:tenant_id>', methods=['GET'])
@token_required
def get_tenant(tenant_id):
    """Get a specific tenant (must be a member)."""
    user = request.current_user
    role = user.get_tenant_role(tenant_id)
    if not role:
        return jsonify({'error': '无权访问该租户'}), 403

    from models.tenant import Tenant
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({'error': '租户不存在'}), 404

    d = tenant.to_dict()
    d['role'] = role
    return jsonify({'tenant': d})


# ==================== Switch Tenant ====================

@tenant_bp.route('/switch', methods=['POST'])
@token_required
@limiter.limit("30 per minute")
def switch_tenant():
    """Switch the user's current tenant. Returns new JWT with updated tenant_id."""
    user = request.current_user
    data = request.get_json()

    tenant_id = data.get('tenant_id')
    if not tenant_id:
        return jsonify({'error': '请指定租户 ID'}), 400

    tenant, error = tenant_service.switch_tenant(user.id, tenant_id)
    if error:
        return jsonify({'error': error}), 400

    # Issue new JWT with updated tenant_id
    from utils.jwt_helper import create_tokens
    ua = request.headers.get('User-Agent', '')
    ip = request.remote_addr or ''
    tokens = create_tokens(user.id, device_info=ua, ip_address=ip)

    # Inject tenant_id into the access token
    import jwt as pyjwt
    from flask import current_app
    access_payload = pyjwt.decode(
        tokens['access_token'],
        current_app.config['JWT_SECRET_KEY'],
        algorithms=['HS256']
    )
    access_payload['tenant_id'] = tenant.id
    access_payload['role'] = user.get_tenant_role(tenant.id)
    tokens['access_token'] = pyjwt.encode(
        access_payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

    biz_logger.info(f"User switched tenant: user={user.id} tenant={tenant.id}")
    return jsonify({
        'message': '切换成功',
        'tenant': tenant.to_dict(),
        'role': user.get_tenant_role(tenant.id),
        **tokens,
    })


# ==================== Members ====================

@tenant_bp.route('/<int:tenant_id>/members', methods=['GET'])
@token_required
@require_tenant
def get_members(tenant_id):
    """Get all members of a tenant."""
    user = request.current_user
    if not user.get_tenant_role(tenant_id):
        return jsonify({'error': '无权访问该租户'}), 403

    members = tenant_service.get_tenant_members(tenant_id)
    return jsonify({
        'members': [m.to_dict() for m in members],
        'total': len(members),
    })


@tenant_bp.route('/<int:tenant_id>/members', methods=['POST'])
@token_required
@require_tenant
@require_tenant_role('owner', 'admin')
def add_member(tenant_id):
    """Add a member to the tenant (admin+ only)."""
    data = request.get_json()

    user_id = data.get('user_id')
    email = data.get('email')
    role = data.get('role', 'member')

    if not user_id and not email:
        return jsonify({'error': '请提供 user_id 或 email'}), 400

    # Resolve user by email if provided
    if email and not user_id:
        from models.user import User
        target_user = User.query.filter_by(email=email).first()
        if not target_user:
            return jsonify({'error': '未找到该邮箱对应的用户'}), 404
        user_id = target_user.id

    membership, error = tenant_service.add_member(tenant_id, user_id, role)
    if error:
        return jsonify({'error': error}), 400

    biz_logger.info(f"Member added to tenant: tenant={tenant_id} user={user_id} role={role}")
    return jsonify({
        'message': '成员添加成功',
        'membership': membership.to_dict(),
    }), 201


@tenant_bp.route('/<int:tenant_id>/members/<int:user_id>', methods=['DELETE'])
@token_required
@require_tenant
@require_tenant_role('owner', 'admin')
def remove_member(tenant_id, user_id):
    """Remove a member from the tenant (admin+ only)."""
    success, error = tenant_service.remove_member(tenant_id, user_id)
    if not success:
        return jsonify({'error': error}), 400

    biz_logger.info(f"Member removed from tenant: tenant={tenant_id} user={user_id}")
    return jsonify({'message': '成员已移除'})


@tenant_bp.route('/<int:tenant_id>/members/<int:user_id>', methods=['PUT'])
@token_required
@require_tenant
@require_tenant_role('owner', 'admin')
def update_member_role(tenant_id, user_id):
    """Update a member's role (admin+ only)."""
    data = request.get_json()
    new_role = data.get('role')

    if not new_role:
        return jsonify({'error': '请指定新角色'}), 400

    membership, error = tenant_service.update_member_role(tenant_id, user_id, new_role)
    if error:
        return jsonify({'error': error}), 400

    biz_logger.info(f"Member role updated: tenant={tenant_id} user={user_id} role={new_role}")
    return jsonify({
        'message': '角色更新成功',
        'membership': membership.to_dict(),
    })


@tenant_bp.route('/<int:tenant_id>/transfer', methods=['POST'])
@token_required
@require_tenant
@require_tenant_role('owner')
def transfer_ownership(tenant_id):
    """Transfer tenant ownership (owner only)."""
    data = request.get_json()
    new_owner_id = data.get('new_owner_id')

    if not new_owner_id:
        return jsonify({'error': '请指定新拥有者'}), 400

    success, error = tenant_service.transfer_ownership(tenant_id, new_owner_id)
    if not success:
        return jsonify({'error': error}), 400

    biz_logger.info(f"Ownership transferred: tenant={tenant_id} to={new_owner_id}")
    return jsonify({'message': '所有权转让成功'})
