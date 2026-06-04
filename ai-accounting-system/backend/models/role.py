"""Role-Based Access Control models."""

from datetime import datetime
from extensions import db


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), default='')
    is_system = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    permissions = db.relationship('Permission', secondary='role_permissions', backref='roles')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'is_system': self.is_system,
            'permissions': [p.codename for p in self.permissions]
        }


class Permission(db.Model):
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    codename = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(255), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'codename': self.codename,
            'name': self.name,
            'description': self.description
        }


class RolePermission(db.Model):
    __tablename__ = 'role_permissions'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
    )


# Permission codenames
PERMISSIONS = [
    ('user:list', '用户列表', '查看用户列表'),
    ('user:read', '用户详情', '查看用户详细信息'),
    ('user:update_status', '更新用户状态', '启用/禁用用户'),
    ('user:assign_role', '分配角色', '为用户分配角色'),
    ('transaction:read', '查看交易', '查看交易记录'),
    ('transaction:create', '创建交易', '创建新交易记录'),
    ('transaction:update', '更新交易', '修改交易记录'),
    ('transaction:delete', '删除交易', '删除交易记录'),
    ('ai:call', 'AI 调用', '使用 AI 记账功能'),
    ('ai:agent', 'AI Agent', '使用 AI Agent 功能'),
    ('category:manage', '管理分类', '管理交易分类'),
    ('subscription:manage', '管理订阅', '管理订阅和支付'),
    ('report:export', '导出报告', '导出财务报告'),
    ('audit:read', '查看审计日志', '查看系统审计日志'),
    ('system:config', '系统配置', '修改系统配置'),
]

# Role -> Permission mapping
ROLE_PERMISSIONS_MAP = {
    'owner': [p[0] for p in PERMISSIONS],  # All permissions
    'admin': [
        'user:list', 'user:read', 'user:update_status',
        'transaction:read', 'transaction:create', 'transaction:update', 'transaction:delete',
        'ai:call', 'ai:agent',
        'category:manage', 'subscription:manage',
        'report:export', 'audit:read',
    ],
    'member': [
        'transaction:read', 'transaction:create', 'transaction:update',
        'ai:call', 'ai:agent',
        'report:export',
    ],
    'viewer': [
        'transaction:read',
    ],
}

ROLES = [
    ('owner', '所有者', '系统最高权限，可管理所有功能和用户'),
    ('admin', '管理员', '可管理用户、交易、分类和查看审计日志'),
    ('member', '成员', '可创建和编辑交易记录，使用 AI 功能'),
    ('viewer', '观察者', '仅可查看交易记录'),
]


def seed_roles_and_permissions():
    """Seed roles and permissions if they don't exist."""
    if Role.query.count() > 0:
        return

    # Create permissions
    perm_map = {}
    for codename, name, desc in PERMISSIONS:
        p = Permission(codename=codename, name=name, description=desc)
        db.session.add(p)
        perm_map[codename] = p

    db.session.flush()

    # Create roles with permissions
    for role_name, display_name, desc in ROLES:
        role = Role(name=role_name, display_name=display_name, description=desc)
        db.session.add(role)
        db.session.flush()

        for perm_codename in ROLE_PERMISSIONS_MAP.get(role_name, []):
            rp = RolePermission(role_id=role.id, permission_id=perm_map[perm_codename].id)
            db.session.add(rp)

    db.session.commit()
