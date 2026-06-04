"""TOTP secret model for two-factor authentication."""

import hashlib
from datetime import datetime
from extensions import db


class TotpSecret(db.Model):
    __tablename__ = 'totp_secrets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    secret = db.Column(db.String(255), nullable=False)
    is_enabled = db.Column(db.Boolean, default=False)
    backup_codes = db.Column(db.JSON, nullable=True)  # List of hashed backup codes
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_backup_codes(self, codes):
        """Hash and store backup codes."""
        self.backup_codes = [hashlib.sha256(c.encode()).hexdigest() for c in codes]

    def get_backup_codes(self):
        """Return stored hashed backup codes."""
        return self.backup_codes or []

    def to_dict(self):
        return {
            'id': self.id,
            'is_enabled': self.is_enabled,
            'has_backup_codes': bool(self.backup_codes),
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
