"""Encrypted credential storage model."""

from datetime import datetime
from extensions import db


class EncryptedCredential(db.Model):
    __tablename__ = 'encrypted_credentials'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    encrypted_value = db.Column(db.Text, nullable=False)
    credential_type = db.Column(db.String(50), default='api_key')  # api_key, payment_token, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_user_credential'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'credential_type': self.credential_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
