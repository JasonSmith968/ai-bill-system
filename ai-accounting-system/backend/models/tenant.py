"""Multi-tenant models: Tenant and TenantMember."""

from datetime import datetime
from extensions import db


class Tenant(db.Model):
    """Tenant (organization/workspace) model — the top-level data isolation boundary."""
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=True)

    stripe_customer_id = db.Column(db.String(200), nullable=True)
    stripe_subscription_id = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='active')  # active | suspended | cancelled
    max_members = db.Column(db.Integer, default=5)
    settings = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    members = db.relationship('TenantMember', backref='tenant', lazy='dynamic',
                              cascade='all, delete-orphan')
    owner = db.relationship('User', foreign_keys=[owner_id], backref='owned_tenants')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'owner_id': self.owner_id,
            'plan_id': self.plan_id,
            'status': self.status,
            'max_members': self.max_members,
            'settings': self.settings,
            'member_count': self.members.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantMember(db.Model):
    """Association between users and tenants with a tenant-scoped role."""
    __tablename__ = 'tenant_members'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default='member')  # owner | admin | member | viewer
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_user'),
    )

    # Relationships
    user = db.relationship('User', backref=db.backref('tenant_memberships', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'role': self.role,
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'email': self.user.email,
                'avatar': self.user.get_avatar_url() if self.user else '',
            } if self.user else None,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
        }
