from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar = db.Column(db.String(500), default='')
    phone = db.Column(db.String(20), default='')
    is_admin = db.Column(db.Boolean, default=False)  # Deprecated: use role_id
    is_active = db.Column(db.Boolean, default=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    totp_enabled = db.Column(db.Boolean, default=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=True)
    stripe_customer_id = db.Column(db.String(200), nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic')
    refresh_tokens = db.relationship('RefreshToken', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    login_history = db.relationship('LoginHistory', backref='user', lazy='dynamic')
    password_reset_tokens = db.relationship('PasswordResetToken', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    email_verification_tokens = db.relationship('EmailVerificationToken', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    subscription = db.relationship('Subscription', backref='user', uselist=False, foreign_keys='Subscription.user_id')
    totp_secret = db.relationship('TotpSecret', backref='user', uselist=False)
    tenant = db.relationship('Tenant', foreign_keys=[tenant_id], backref='users')
    role = db.relationship('Role', foreign_keys=[role_id], backref='users')

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def is_locked(self):
        """检查账号是否被锁定"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        # 锁定已过期，自动重置
        if self.locked_until and self.locked_until <= datetime.utcnow():
            self.failed_login_attempts = 0
            self.locked_until = None
            db.session.commit()
        return False

    def record_failed_login(self, max_attempts=5, lockout_minutes=30):
        """记录失败登录尝试"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
        db.session.commit()

    def reset_failed_login(self):
        """重置失败登录计数"""
        self.failed_login_attempts = 0
        self.locked_until = None

    @property
    def role_name(self):
        """Get role name, falling back to is_admin column."""
        if self.role:
            return self.role.name
        return 'owner' if self.is_admin else 'member'

    def has_permission(self, codename):
        """Check if user has a specific permission via their role."""
        if not self.role:
            # Fallback: owners have all permissions
            return self.is_admin
        from models.role import Permission
        perm = Permission.query.filter_by(codename=codename).first()
        if not perm:
            return False
        return perm in self.role.permissions

    def get_permission_codenames(self):
        """Get list of permission codenames for this user's role."""
        if not self.role:
            return []
        return [p.codename for p in self.role.permissions]

    def get_tenant_role(self, tenant_id=None):
        """Get the user's role within a specific tenant (or current tenant)."""
        from flask import g
        if tenant_id is None:
            tenant = getattr(g, 'current_tenant', None)
            tenant_id = tenant.id if tenant else None
        if not tenant_id:
            return None
        from models.tenant import TenantMember
        membership = TenantMember.query.filter_by(
            tenant_id=tenant_id, user_id=self.id
        ).first()
        return membership.role if membership else None

    def get_tenants(self):
        """Get all tenants this user belongs to."""
        from models.tenant import Tenant, TenantMember
        memberships = TenantMember.query.filter_by(user_id=self.id).all()
        tenant_ids = [m.tenant_id for m in memberships]
        return Tenant.query.filter(Tenant.id.in_(tenant_ids)).all() if tenant_ids else []

    def get_plan(self):
        """获取用户当前套餐，默认返回免费套餐"""
        from models.plan import Plan
        if self.subscription and self.subscription.status == 'active' and self.subscription.plan:
            return self.subscription.plan
        # Default to free plan
        return Plan.query.filter_by(name='free').first()

    def get_plan_name(self):
        """获取用户当前套餐名称"""
        plan = self.get_plan()
        return plan.name if plan else 'free'

    def get_avatar_url(self):
        """Resolve avatar storage key to a URL."""
        if not self.avatar:
            return ''
        # Backward compat: old-style paths start with /uploads/
        if self.avatar.startswith('/uploads/'):
            return self.avatar
        try:
            from services.storage import get_storage
            return get_storage().get_url(self.avatar)
        except Exception:
            return self.avatar

    def to_dict(self):
        """转换为字典"""
        plan = self.get_plan()
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'avatar': self.get_avatar_url(),
            'phone': self.phone,
            'is_admin': self.is_admin or self.role_name in ('owner', 'admin'),
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'failed_login_attempts': self.failed_login_attempts,
            'locked_until': self.locked_until.isoformat() if self.locked_until else None,
            'role': self.role_name,
            'permissions': self.get_permission_codenames(),
            'totp_enabled': self.totp_enabled,
            'plan': plan.to_dict() if plan else None,
            'plan_name': self.get_plan_name(),
            'tenant_id': self.tenant_id,
            'tenants': [{'id': t.id, 'name': t.name, 'slug': t.slug, 'role': self.get_tenant_role(t.id)} for t in self.get_tenants()],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
