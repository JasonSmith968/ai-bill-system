"""User subscription model."""

from datetime import datetime
from extensions import db


class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # deprecated: use tenant_id
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, cancelled, expired, past_due
    billing_cycle = db.Column(db.String(20), default='monthly')  # monthly, yearly
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    stripe_subscription_id = db.Column(db.String(200), nullable=True)
    stripe_customer_id = db.Column(db.String(200), nullable=True)
    alipay_trade_no = db.Column(db.String(200), nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'plan': self.plan.to_dict() if self.plan else None,
            'status': self.status,
            'billing_cycle': self.billing_cycle,
            'current_period_start': self.current_period_start.isoformat() if self.current_period_start else None,
            'current_period_end': self.current_period_end.isoformat() if self.current_period_end else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
