from datetime import datetime
from extensions import db


class EmailVerificationToken(db.Model):
    """邮箱验证令牌模型"""
    __tablename__ = 'email_verification_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
