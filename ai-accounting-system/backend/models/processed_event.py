"""Processed Stripe event tracking for webhook idempotency.

Stores event IDs to prevent duplicate processing of Stripe webhook events.
Stripe may deliver the same event multiple times — this table ensures
each event is processed exactly once.
"""

from datetime import datetime
from extensions import db


class ProcessedEvent(db.Model):
    __tablename__ = 'processed_events'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(128), nullable=False, unique=True, index=True)
    event_type = db.Column(db.String(64), nullable=False)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def is_processed(cls, event_id: str) -> bool:
        """Check if an event has already been processed."""
        return cls.query.filter_by(event_id=event_id).first() is not None

    @classmethod
    def mark_processed(cls, event_id: str, event_type: str) -> 'ProcessedEvent':
        """Mark an event as processed."""
        record = cls(event_id=event_id, event_type=event_type)
        db.session.add(record)
        # Don't commit here — caller should commit as part of their transaction
        return record

    def to_dict(self):
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
        }
