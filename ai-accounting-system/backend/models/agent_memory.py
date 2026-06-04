"""Agent memory model for persistent user financial profiles and habits."""

from datetime import datetime
from extensions import db


class AgentMemory(db.Model):
    __tablename__ = 'agent_memories'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    memory_type = db.Column(db.String(32), nullable=False, index=True)  # preference/habit/profile/fact
    key = db.Column(db.String(128), nullable=False)
    value = db.Column(db.JSON, nullable=False)
    confidence = db.Column(db.Float, default=0.8)  # 0-1
    source = db.Column(db.String(16), default='inferred')  # inferred/explicit
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'key', name='uq_user_memory_key'),
    )

    @classmethod
    def get_user_memories(cls, user_id, memory_type=None):
        """Retrieve all memories for a user, optionally filtered by type."""
        q = cls.query.filter_by(user_id=user_id)
        if memory_type:
            q = q.filter_by(memory_type=memory_type)
        return q.order_by(cls.updated_at.desc()).all()

    @classmethod
    def get_by_key(cls, user_id, key):
        """Retrieve a specific memory by user and key."""
        return cls.query.filter_by(user_id=user_id, key=key).first()

    def update_confidence(self, new_evidence):
        """Bayesian confidence update when new evidence arrives.

        If new_evidence is True, confidence increases toward 1.
        If False, confidence decreases toward 0.
        """
        if new_evidence:
            self.confidence = min(self.confidence + (1 - self.confidence) * 0.3, 1.0)
        else:
            self.confidence = max(self.confidence - self.confidence * 0.4, 0.0)
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        return {
            'id': self.id,
            'memory_type': self.memory_type,
            'key': self.key,
            'value': self.value,
            'confidence': self.confidence,
            'source': self.source,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
