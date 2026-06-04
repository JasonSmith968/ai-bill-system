"""AI usage tracking model."""

from datetime import datetime, date
from extensions import db


class UsageLog(db.Model):
    __tablename__ = 'usage_logs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    period = db.Column(db.String(7), nullable=False, index=True)  # YYYY-MM format
    calls_used = db.Column(db.Integer, default=0)
    tokens_used = db.Column(db.Integer, default=0)
    calls_limit = db.Column(db.Integer, default=50)
    token_limit = db.Column(db.Integer, default=100000)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'period', name='uq_user_period'),
    )

    @staticmethod
    def get_or_create_current(user_id, calls_limit=50, token_limit=100000):
        """Get or create usage log for the current month."""
        current_period = date.today().strftime('%Y-%m')
        usage = UsageLog.query.filter_by(user_id=user_id, period=current_period).first()
        if not usage:
            from flask import g
            tenant = getattr(g, 'current_tenant', None)
            usage = UsageLog(
                user_id=user_id,
                tenant_id=tenant.id if tenant else None,
                period=current_period,
                calls_used=0,
                tokens_used=0,
                calls_limit=calls_limit,
                token_limit=token_limit
            )
            db.session.add(usage)
            db.session.commit()
        return usage

    def to_dict(self):
        return {
            'id': self.id,
            'period': self.period,
            'calls_used': self.calls_used,
            'tokens_used': self.tokens_used,
            'calls_limit': self.calls_limit,
            'token_limit': self.token_limit,
            'calls_remaining': max(0, self.calls_limit - self.calls_used),
            'tokens_remaining': max(0, self.token_limit - self.tokens_used),
            'calls_pct': round(self.calls_used / max(self.calls_limit, 1) * 100, 1),
            'tokens_pct': round(self.tokens_used / max(self.token_limit, 1) * 100, 1)
        }
