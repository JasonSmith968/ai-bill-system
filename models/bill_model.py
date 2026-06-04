from models import db

class Bill(db.Model):

    __tablename__ = "bills"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(100))

    amount = db.Column(db.Float)

    category = db.Column(db.String(50))

    created_at = db.Column(db.String(30))

    user_id = db.Column(db.Integer)