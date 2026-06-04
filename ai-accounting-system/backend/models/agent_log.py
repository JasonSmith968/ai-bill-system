"""Agent execution log model."""

from datetime import datetime
from extensions import db


class AgentExecutionLog(db.Model):
    __tablename__ = 'agent_execution_logs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    request_id = db.Column(db.String(32), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    agent_name = db.Column(db.String(50), nullable=False)
    success = db.Column(db.Boolean, default=True)
    duration_ms = db.Column(db.Float, default=0)
    error_message = db.Column(db.Text, nullable=True)
    output_keys = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # LLM tracing fields (from llm_tracer)
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    cost_cents = db.Column(db.Float, default=0.0)
    model = db.Column(db.String(64), nullable=True)
