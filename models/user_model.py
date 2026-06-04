from models import db

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True)

    password = db.Column(db.String(255))

    created_at = db.Column(db.DateTime)