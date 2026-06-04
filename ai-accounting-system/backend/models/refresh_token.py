from datetime import datetime
from extensions import db


class RefreshToken(db.Model):
    """刷新令牌模型 - 支持令牌轮换和撤销"""
    __tablename__ = 'refresh_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)
    token_family = db.Column(db.String(36), nullable=False, index=True)
    device_info = db.Column(db.String(256), default='')
    ip_address = db.Column(db.String(45), default='')
    is_revoked = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'jti': self.jti,
            'device_info': self.device_info,
            'ip_address': self.ip_address,
            'is_revoked': self.is_revoked,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat()
        }
