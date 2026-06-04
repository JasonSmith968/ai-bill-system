"""Prompt template model for managed system prompts."""

import re
from datetime import datetime
from extensions import db


class PromptTemplate(db.Model):
    __tablename__ = 'prompt_templates'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    agent_name = db.Column(db.String(64), nullable=True, index=True)
    template = db.Column(db.Text, nullable=False)
    variables = db.Column(db.JSON, nullable=True)  # list of variable names
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    ab_weight = db.Column(db.Float, default=0.0)  # A/B testing weight (0 = not an A/B variant)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('name', 'version', name='uq_prompt_name_version'),
    )

    def render(self, **kwargs):
        """Render template with variable substitution.

        Supports {{variable}} syntax. Missing variables are left as-is.
        """
        result = self.template
        for key, value in kwargs.items():
            result = result.replace('{{' + key + '}}', str(value))
        return result

    @classmethod
    def get_active(cls, name, agent_name=None):
        """Get the active template by name, optionally filtered by agent."""
        q = cls.query.filter_by(name=name, is_active=True)
        if agent_name:
            q = q.filter_by(agent_name=agent_name)
        return q.first()

    @classmethod
    def get_agent_templates(cls, agent_name):
        """Get all active templates for a specific agent."""
        return cls.query.filter_by(agent_name=agent_name, is_active=True).all()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'agent_name': self.agent_name,
            'template': self.template,
            'variables': self.variables,
            'version': self.version,
            'is_active': self.is_active,
            'ab_weight': self.ab_weight,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
