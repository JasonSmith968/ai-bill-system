"""TaskRecord — persistent log of async Celery tasks."""

from datetime import datetime
from extensions import db


class TaskRecord(db.Model):
    __tablename__ = 'task_records'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    task_id = db.Column(db.String(36), unique=True, nullable=False, index=True)  # Celery task UUID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    task_type = db.Column(db.String(20), nullable=False, index=True)  # ai | ocr | email | report
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)  # pending | running | success | failed
    result = db.Column(db.JSON, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('task_records', lazy='dynamic'))

    @property
    def duration_ms(self):
        """Calculate task duration in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        if self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds() * 1000
        return 0

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'task_type': self.task_type,
            'status': self.status,
            'result': self.result,
            'error': self.error,
            'duration_ms': round(self.duration_ms, 0),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def get_user_tasks(cls, user_id, task_type=None, status=None, limit=20):
        """Query tasks for a user with optional filters."""
        q = cls.query.filter_by(user_id=user_id)
        if task_type:
            q = q.filter_by(task_type=task_type)
        if status:
            q = q.filter_by(status=status)
        return q.order_by(cls.created_at.desc()).limit(limit).all()

    def __repr__(self):
        return f'<TaskRecord {self.task_id} [{self.status}]>'
