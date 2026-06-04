"""Referral and invite reward models."""

from datetime import datetime
from extensions import db


class Referral(db.Model):
    """Referral link tracking."""
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    referred_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    referral_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default='pending')  # pending, registered, converted, rewarded
    reward_type = db.Column(db.String(30), nullable=True)  # free_days, credits, discount
    reward_value = db.Column(db.Integer, default=0)
    referred_email = db.Column(db.String(200), nullable=True)
    registered_at = db.Column(db.DateTime, nullable=True)
    converted_at = db.Column(db.DateTime, nullable=True)
    rewarded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_made')
    referred = db.relationship('User', foreign_keys=[referred_id], backref='referral_source')

    def to_dict(self):
        return {
            'id': self.id,
            'referral_code': self.referral_code,
            'status': self.status,
            'reward_type': self.reward_type,
            'reward_value': self.reward_value,
            'referred_email': self.referred_email,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'converted_at': self.converted_at.isoformat() if self.converted_at else None,
            'rewarded_at': self.rewarded_at.isoformat() if self.rewarded_at else None,
            'created_at': self.created_at.isoformat(),
        }


class InviteReward(db.Model):
    """Invite reward configuration and tracking."""
    __tablename__ = 'invite_rewards'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    trigger = db.Column(db.String(30), nullable=False)  # signup, first_payment, usage_milestone
    referrer_reward_type = db.Column(db.String(30), nullable=False)  # free_days, credits, discount_pct
    referrer_reward_value = db.Column(db.Integer, default=0)
    referred_reward_type = db.Column(db.String(30), nullable=True)
    referred_reward_value = db.Column(db.Integer, default=0)
    max_rewards = db.Column(db.Integer, default=0)  # 0 = unlimited
    is_active = db.Column(db.Boolean, default=True)
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'trigger': self.trigger,
            'referrer_reward_type': self.referrer_reward_type,
            'referrer_reward_value': self.referrer_reward_value,
            'referred_reward_type': self.referred_reward_type,
            'referred_reward_value': self.referred_reward_value,
            'max_rewards': self.max_rewards,
            'is_active': self.is_active,
        }


class Affiliate(db.Model):
    """Affiliate partner tracking."""
    __tablename__ = 'affiliates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    affiliate_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    commission_type = db.Column(db.String(20), default='percentage')  # percentage, fixed
    commission_rate = db.Column(db.Float, default=0.20)  # 20% default
    cookie_days = db.Column(db.Integer, default=30)
    status = db.Column(db.String(20), default='active')  # active, suspended, banned
    total_clicks = db.Column(db.Integer, default=0)
    total_conversions = db.Column(db.Integer, default=0)
    total_revenue_cents = db.Column(db.BigInteger, default=0)
    total_commission_cents = db.Column(db.BigInteger, default=0)
    paid_commission_cents = db.Column(db.BigInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='affiliate_profile')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'affiliate_code': self.affiliate_code,
            'commission_type': self.commission_type,
            'commission_rate': self.commission_rate,
            'status': self.status,
            'total_clicks': self.total_clicks,
            'total_conversions': self.total_conversions,
            'total_revenue_cents': self.total_revenue_cents,
            'total_commission_cents': self.total_commission_cents,
            'paid_commission_cents': self.paid_commission_cents,
            'unpaid_cents': self.total_commission_cents - self.paid_commission_cents,
            'created_at': self.created_at.isoformat(),
        }


class AffiliateClick(db.Model):
    """Affiliate link click tracking."""
    __tablename__ = 'affiliate_clicks'

    id = db.Column(db.Integer, primary_key=True)
    affiliate_id = db.Column(db.Integer, db.ForeignKey('affiliates.id'), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    referrer_url = db.Column(db.String(500), nullable=True)
    landing_page = db.Column(db.String(500), nullable=True)
    converted = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    affiliate = db.relationship('Affiliate', backref='clicks')

    def to_dict(self):
        return {
            'id': self.id,
            'affiliate_id': self.affiliate_id,
            'converted': self.converted,
            'created_at': self.created_at.isoformat(),
        }


class AffiliateConversion(db.Model):
    """Affiliate conversion tracking."""
    __tablename__ = 'affiliate_conversions'

    id = db.Column(db.Integer, primary_key=True)
    affiliate_id = db.Column(db.Integer, db.ForeignKey('affiliates.id'), nullable=False, index=True)
    click_id = db.Column(db.Integer, db.ForeignKey('affiliate_clicks.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=True)
    revenue_cents = db.Column(db.Integer, default=0)
    commission_cents = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, approved, paid, rejected
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    affiliate = db.relationship('Affiliate', backref='conversions')
    click = db.relationship('AffiliateClick')
    user = db.relationship('User')
    subscription = db.relationship('Subscription')

    def to_dict(self):
        return {
            'id': self.id,
            'affiliate_id': self.affiliate_id,
            'user_id': self.user_id,
            'revenue_cents': self.revenue_cents,
            'commission_cents': self.commission_cents,
            'status': self.status,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat(),
        }
