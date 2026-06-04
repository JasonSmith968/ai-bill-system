from datetime import datetime
from extensions import db


class Category(db.Model):
    """Category model."""
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # income / expense
    icon = db.Column(db.String(50), default='tag')
    color = db.Column(db.String(20), default='#6B7280')
    is_default = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'icon': self.icon,
            'color': self.color,
            'is_default': self.is_default
        }


class Transaction(db.Model):
    """Transaction model."""
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False)  # income / expense
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    category = db.relationship('Category', backref='transactions')
    description = db.Column(db.String(200), default='')
    note = db.Column(db.String(500), default='')
    date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # AI fields
    ai_generated = db.Column(db.Boolean, default=False)
    ai_confidence = db.Column(db.Float, default=0.0)
    original_text = db.Column(db.Text, default='')

    # Receipt / OCR fields
    merchant = db.Column(db.String(100), default='')
    receipt_image = db.Column(db.String(500), default='')
    ocr_text = db.Column(db.Text, default='')

    def get_receipt_image_url(self):
        """Resolve receipt image storage key to a URL."""
        if not self.receipt_image:
            return ''
        if self.receipt_image.startswith('/uploads/'):
            return self.receipt_image
        try:
            from services.storage import get_storage
            return get_storage().get_url(self.receipt_image)
        except Exception:
            return self.receipt_image

    def to_dict(self):
        # Defensive: catch ObjectDeletedError when category was deleted
        # between the Transaction query and this serialization.
        category_data = None
        if self.category_id is not None:
            try:
                if self.category is not None:
                    category_data = self.category.to_dict()
            except Exception:
                # Category row deleted or inaccessible — use ID only
                try:
                    from utils.db_observability import record_orm_error
                    record_orm_error('ObjectDeletedError')
                except Exception:
                    pass
                category_data = {'id': self.category_id, 'name': '(已删除)', 'type': self.type}

        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'type': self.type,
            'amount': float(self.amount),
            'category': category_data,
            'category_id': self.category_id,
            'description': self.description,
            'note': self.note,
            'date': self.date.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'ai_generated': self.ai_generated,
            'ai_confidence': self.ai_confidence,
            'original_text': self.original_text,
            'merchant': self.merchant,
            'receipt_image': self.get_receipt_image_url(),
            'ocr_text': self.ocr_text,
        }
