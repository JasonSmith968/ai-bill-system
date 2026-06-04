from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# =========================
# 用户表
# =========================
class User(db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )

# =========================
# 账单表
# =========================
class Bill(db.Model):

    __tablename__ = "bills"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        nullable=False
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    category = db.Column(
        db.String(100),
        default="其他"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )