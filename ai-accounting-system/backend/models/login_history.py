from datetime import datetime
from extensions import db


class LoginHistory(db.Model):
    """登录历史模型"""
    __tablename__ = 'login_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    ip_address = db.Column(db.String(45), default='')
    user_agent = db.Column(db.String(500), default='')
    device_type = db.Column(db.String(50), default='')
    browser = db.Column(db.String(100), default='')
    os = db.Column(db.String(100), default='')
    login_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    success = db.Column(db.Boolean, default=True)
    failure_reason = db.Column(db.String(100), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'device_type': self.device_type,
            'browser': self.browser,
            'os': self.os,
            'login_at': self.login_at.isoformat(),
            'success': self.success,
            'failure_reason': self.failure_reason
        }
