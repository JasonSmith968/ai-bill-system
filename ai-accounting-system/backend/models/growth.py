"""Growth system models: onboarding, email lifecycle, nudges."""

from datetime import datetime
from extensions import db


class OnboardingStep(db.Model):
    """User onboarding progress tracking."""
    __tablename__ = 'onboarding_steps'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    step_key = db.Column(db.String(50), nullable=False)  # welcome, create_first, connect_bank, invite_team, setup_budget
    status = db.Column(db.String(20), default='pending')  # pending, skipped, completed
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='onboarding_steps')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'step_key', name='uq_user_onboarding_step'),
    )

    def to_dict(self):
        return {
            'step_key': self.step_key,
            'status': self.status,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class OnboardingFlow(db.Model):
    """Onboarding flow configuration."""
    __tablename__ = 'onboarding_flows'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    steps = db.Column(db.JSON, nullable=False)  # [{key, title, description, action, optional}]
    target_segment = db.Column(db.String(50), default='all')  # all, free, paid, enterprise
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'steps': self.steps,
            'target_segment': self.target_segment,
            'is_active': self.is_active,
        }


class EmailTemplate(db.Model):
    """Email template for lifecycle automation."""
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    body_text = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False)  # onboarding, retention, engagement, transactional
    language = db.Column(db.String(10), default='zh-CN')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'subject': self.subject,
            'category': self.category,
            'is_active': self.is_active,
        }


class EmailLog(db.Model):
    """Email send log."""
    __tablename__ = 'email_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    template_name = db.Column(db.String(100), nullable=False)
    recipient = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), default='queued')  # queued, sent, delivered, opened, clicked, failed
    error_message = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    opened_at = db.Column(db.DateTime, nullable=True)
    clicked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='email_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'template_name': self.template_name,
            'recipient': self.recipient,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
        }


class GrowthEvent(db.Model):
    """Growth event tracking for analytics."""
    __tablename__ = 'growth_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)  # signup, invite_sent, invite_accepted, upgrade, churn, nudge_sent, nudge_clicked
    event_data = db.Column(db.JSON, nullable=True)
    source = db.Column(db.String(50), nullable=True)  # referral, affiliate, organic, paid
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='growth_events')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'event_type': self.event_type,
            'event_data': self.event_data,
            'source': self.source,
            'created_at': self.created_at.isoformat(),
        }


class NudgeRule(db.Model):
    """AI usage nudge rule configuration."""
    __tablename__ = 'nudge_rules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    trigger_condition = db.Column(db.JSON, nullable=False)  # {metric, operator, value, period}
    nudge_type = db.Column(db.String(30), nullable=False)  # email, in_app, push
    nudge_content = db.Column(db.JSON, nullable=False)  # {title, message, cta, cta_url}
    cooldown_hours = db.Column(db.Integer, default=72)
    max_sends = db.Column(db.Integer, default=3)
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'trigger_condition': self.trigger_condition,
            'nudge_type': self.nudge_type,
            'nudge_content': self.nudge_content,
            'cooldown_hours': self.cooldown_hours,
            'max_sends': self.max_sends,
            'is_active': self.is_active,
        }


class NudgeLog(db.Model):
    """Nudge send log."""
    __tablename__ = 'nudge_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('nudge_rules.id'), nullable=False)
    nudge_type = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), default='sent')  # sent, delivered, clicked, dismissed
    clicked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='nudge_logs')
    rule = db.relationship('NudgeRule', backref='logs')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'rule_id': self.rule_id,
            'nudge_type': self.nudge_type,
            'status': self.status,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
            'created_at': self.created_at.isoformat(),
        }
