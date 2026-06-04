"""Tenant service — business logic for tenant CRUD and member management."""

import re
import logging
from datetime import datetime
from extensions import db
from models.tenant import Tenant, TenantMember
from models.user import User

logger = logging.getLogger(__name__)


def generate_slug(name):
    """Generate a URL-safe slug from a tenant name.

    For Chinese names, falls back to 'tenant-{hash}'.
    """
    # Try ASCII slug first
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    if slug and len(slug) >= 2:
        return slug[:50]
    # Fallback for non-ASCII names (Chinese, etc.)
    import hashlib
    return f"tenant-{hashlib.md5(name.encode()).hexdigest()[:8]}"


def ensure_unique_slug(slug, exclude_id=None):
    """Ensure slug is unique by appending a numeric suffix if needed."""
    original = slug
    counter = 1
    while True:
        q = Tenant.query.filter_by(slug=slug)
        if exclude_id:
            q = q.filter(Tenant.id != exclude_id)
        if not q.first():
            return slug
        counter += 1
        slug = f"{original}-{counter}"


def create_tenant(name, owner_id, max_members=5):
    """Create a new tenant, add owner as member, create default categories.

    Returns:
        (tenant, error) tuple
    """
    user = User.query.get(owner_id)
    if not user:
        return None, '用户不存在'

    # Generate unique slug
    base_slug = generate_slug(name)
    slug = ensure_unique_slug(base_slug)

    # Create tenant
    tenant = Tenant(
        name=name,
        slug=slug,
        owner_id=owner_id,
        max_members=max_members,
        status='active',
    )
    db.session.add(tenant)
    db.session.flush()  # Get tenant.id

    # Add owner as member
    membership = TenantMember(
        tenant_id=tenant.id,
        user_id=owner_id,
        role='owner',
    )
    db.session.add(membership)

    # Set user's current tenant
    user.tenant_id = tenant.id

    # Create default categories for this tenant
    _create_default_categories(tenant.id)

    db.session.commit()

    logger.info(f"Tenant created: id={tenant.id} name={name} owner={owner_id}")
    return tenant, None


def add_member(tenant_id, user_id, role='member'):
    """Add a user to a tenant.

    Returns:
        (membership, error) tuple
    """
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return None, '租户不存在'

    user = User.query.get(user_id)
    if not user:
        return None, '用户不存在'

    # Check if already a member
    existing = TenantMember.query.filter_by(
        tenant_id=tenant_id, user_id=user_id
    ).first()
    if existing:
        return None, '用户已是该租户成员'

    # Check member limit
    current_count = TenantMember.query.filter_by(tenant_id=tenant_id).count()
    if current_count >= tenant.max_members:
        return None, f'成员数量已达到上限 ({tenant.max_members})'

    membership = TenantMember(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
    )
    db.session.add(membership)
    db.session.commit()

    logger.info(f"Member added: tenant={tenant_id} user={user_id} role={role}")
    return membership, None


def remove_member(tenant_id, user_id):
    """Remove a user from a tenant.

    Returns:
        (success, error) tuple
    """
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return False, '租户不存在'

    # Cannot remove the owner
    if tenant.owner_id == user_id:
        return False, '不能移除租户拥有者'

    membership = TenantMember.query.filter_by(
        tenant_id=tenant_id, user_id=user_id
    ).first()
    if not membership:
        return False, '该用户不是租户成员'

    db.session.delete(membership)

    # If this was the user's current tenant, clear it
    user = User.query.get(user_id)
    if user and user.tenant_id == tenant_id:
        # Switch to another tenant if available
        other = TenantMember.query.filter_by(user_id=user_id).first()
        user.tenant_id = other.tenant_id if other else None

    db.session.commit()

    logger.info(f"Member removed: tenant={tenant_id} user={user_id}")
    return True, None


def get_tenant_members(tenant_id):
    """Get all members of a tenant."""
    return TenantMember.query.filter_by(tenant_id=tenant_id) \
        .order_by(TenantMember.joined_at).all()


def update_member_role(tenant_id, user_id, new_role):
    """Update a member's role within a tenant.

    Returns:
        (membership, error) tuple
    """
    valid_roles = ('admin', 'member', 'viewer')
    if new_role not in valid_roles:
        return None, f'无效角色，可选: {", ".join(valid_roles)}'

    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return None, '租户不存在'

    # Cannot change owner's role via this method
    if tenant.owner_id == user_id:
        return None, '不能修改拥有者的角色'

    membership = TenantMember.query.filter_by(
        tenant_id=tenant_id, user_id=user_id
    ).first()
    if not membership:
        return None, '该用户不是租户成员'

    membership.role = new_role
    db.session.commit()

    logger.info(f"Member role updated: tenant={tenant_id} user={user_id} role={new_role}")
    return membership, None


def transfer_ownership(tenant_id, new_owner_id):
    """Transfer tenant ownership to another member.

    Returns:
        (success, error) tuple
    """
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return False, '租户不存在'

    new_owner_membership = TenantMember.query.filter_by(
        tenant_id=tenant_id, user_id=new_owner_id
    ).first()
    if not new_owner_membership:
        return False, '新拥有者必须是租户成员'

    old_owner_id = tenant.owner_id

    # Update tenant owner
    tenant.owner_id = new_owner_id

    # Update roles
    new_owner_membership.role = 'owner'

    old_owner_membership = TenantMember.query.filter_by(
        tenant_id=tenant_id, user_id=old_owner_id
    ).first()
    if old_owner_membership:
        old_owner_membership.role = 'admin'

    db.session.commit()

    logger.info(f"Ownership transferred: tenant={tenant_id} from={old_owner_id} to={new_owner_id}")
    return True, None


def get_user_tenants(user_id):
    """Get all tenants a user belongs to."""
    memberships = TenantMember.query.filter_by(user_id=user_id).all()
    tenant_ids = [m.tenant_id for m in memberships]
    if not tenant_ids:
        return []
    return Tenant.query.filter(Tenant.id.in_(tenant_ids)).all()


def switch_tenant(user_id, tenant_id):
    """Switch a user's current tenant.

    Returns:
        (tenant, error) tuple
    """
    # Verify membership
    membership = TenantMember.query.filter_by(
        tenant_id=tenant_id, user_id=user_id
    ).first()
    if not membership:
        return None, '您不是该租户的成员'

    tenant = Tenant.query.get(tenant_id)
    if not tenant or tenant.status != 'active':
        return None, '租户不存在或已停用'

    user = User.query.get(user_id)
    if user:
        user.tenant_id = tenant_id
        db.session.commit()

    return tenant, None


def _create_default_categories(tenant_id):
    """Create default expense and income categories for a new tenant."""
    from models.transaction import Category

    default_categories = [
        {'name': '餐饮', 'type': 'expense', 'icon': 'utensils', 'color': '#EF4444'},
        {'name': '交通', 'type': 'expense', 'icon': 'car', 'color': '#F59E0B'},
        {'name': '购物', 'type': 'expense', 'icon': 'shopping-bag', 'color': '#8B5CF6'},
        {'name': '娱乐', 'type': 'expense', 'icon': 'gamepad', 'color': '#EC4899'},
        {'name': '住房', 'type': 'expense', 'icon': 'home', 'color': '#3B82F6'},
        {'name': '医疗', 'type': 'expense', 'icon': 'hospital', 'color': '#10B981'},
        {'name': '教育', 'type': 'expense', 'icon': 'book', 'color': '#6366F1'},
        {'name': '通讯', 'type': 'expense', 'icon': 'phone', 'color': '#14B8A6'},
        {'name': '其他', 'type': 'expense', 'icon': 'tag', 'color': '#6B7280'},
        {'name': '工资', 'type': 'income', 'icon': 'money-bill', 'color': '#22C55E'},
        {'name': '奖金', 'type': 'income', 'icon': 'gift', 'color': '#F59E0B'},
        {'name': '投资', 'type': 'income', 'icon': 'chart-line', 'color': '#3B82F6'},
        {'name': '兼职', 'type': 'income', 'icon': 'briefcase', 'color': '#8B5CF6'},
        {'name': '红包', 'type': 'income', 'icon': 'envelope', 'color': '#EF4444'},
        {'name': '其他', 'type': 'income', 'icon': 'tag', 'color': '#6B7280'},
    ]
    for cat in default_categories:
        c = Category(tenant_id=tenant_id, is_default=True, **cat)
        db.session.add(c)
