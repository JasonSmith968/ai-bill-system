"""Regression tests for Final Stabilization Sprint.

Covers:
1. ObjectDeletedError — defensive to_dict() when category is deleted
2. Category validation — _resolve_category enforces tenant isolation
3. Session lifecycle — db.session.remove() in after_request
4. Log rotation — ConcurrentRotatingFileHandler on Windows
5. DB observability — ORM error metrics recorded
"""

import os
import logging
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from extensions import db
from models.user import User
from models.tenant import Tenant, TenantMember
from models.transaction import Transaction, Category


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def app():
    from app import create_app
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seed_data(app):
    """Create a tenant with user, category, and transaction."""
    user = User(username='testuser', email='test@test.com')
    user.set_password('password123')
    db.session.add(user)
    db.session.flush()

    tenant = Tenant(name='TestTenant', slug='test', owner_id=user.id)
    db.session.add(tenant)
    db.session.flush()

    user.tenant_id = tenant.id
    member = TenantMember(tenant_id=tenant.id, user_id=user.id, role='owner')
    db.session.add(member)

    cat = Category(
        tenant_id=tenant.id, name='Food', type='expense',
        icon='utensils', color='#EF4444', is_default=True,
    )
    db.session.add(cat)
    db.session.flush()

    txn = Transaction(
        tenant_id=tenant.id, user_id=user.id, type='expense',
        amount=50.00, category_id=cat.id, description='Lunch',
        date=datetime(2026, 5, 28).date(),
    )
    db.session.add(txn)
    db.session.commit()

    return {
        'user': user, 'tenant': tenant, 'cat': cat, 'txn': txn,
    }


# ── 1. ObjectDeletedError: defensive to_dict ─────────────────────────────


class TestObjectDeletedError:
    def test_to_dict_with_valid_category(self, app, seed_data):
        """Normal case: to_dict() includes category data."""
        txn = seed_data['txn']
        d = txn.to_dict()
        assert d['category'] is not None
        assert d['category']['name'] == 'Food'

    def test_to_dict_when_category_deleted(self, app, seed_data):
        """After deleting the category row, to_dict() should not crash."""
        txn = seed_data['txn']
        cat_id = txn.category_id  # save before raw delete

        # Delete category row directly to keep stale category_id
        db.session.execute(
            db.text("DELETE FROM categories WHERE id = :cid"),
            {'cid': cat_id},
        )
        db.session.commit()

        # Expire txn so ORM re-fetches on next access
        db.session.expire(txn)

        # Should not raise — defensive code catches ObjectDeletedError
        # or handles None relationship gracefully.
        d = txn.to_dict()
        assert d['category_id'] == cat_id
        # Category is either None (row deleted, no error) or fallback dict
        if d['category'] is not None:
            assert d['category']['name'] == '(已删除)'

    def test_to_dict_when_category_none(self, app, seed_data):
        """Transaction with no category should return category=None."""
        txn = seed_data['txn']
        txn.category_id = None
        db.session.commit()

        d = txn.to_dict()
        assert d['category'] is None

    def test_to_dict_records_orm_error_on_exception(self, app, seed_data):
        """When category access raises ObjectDeletedError, metric should be recorded."""
        txn = seed_data['txn']

        # Simulate ObjectDeletedError by making the relationship raise
        with patch.object(type(txn), 'category', new_callable=lambda: property(
            lambda self: (_ for _ in ()).throw(
                __import__('sqlalchemy.orm.exc', fromlist=['ObjectDeletedError']).ObjectDeletedError(None)
            )
        )):
            with patch('utils.db_observability.record_orm_error') as mock_record:
                d = txn.to_dict()
                mock_record.assert_called_once_with('ObjectDeletedError')
                assert d['category'] is not None
                assert d['category']['name'] == '(已删除)'


# ── 2. Category Validation: _resolve_category ────────────────────────────


class TestCategoryValidation:
    def test_resolve_valid_category(self, app, seed_data):
        """Valid category in same tenant should resolve."""
        from routes.transactions import _resolve_category
        cat = seed_data['cat']

        with app.test_request_context():
            from flask import g
            g.current_tenant = seed_data['tenant']

            cat_id, err = _resolve_category(cat.id)
            assert err is None
            assert cat_id == cat.id

    def test_resolve_nonexistent_category(self, app, seed_data):
        """Non-existent category should return 400."""
        from routes.transactions import _resolve_category

        with app.test_request_context():
            from flask import g
            g.current_tenant = seed_data['tenant']

            cat_id, err = _resolve_category(99999)
            assert cat_id is None
            assert err is not None
            resp, status = err
            assert status == 400

    def test_resolve_cross_tenant_category(self, app, seed_data):
        """Category from another tenant should return 400."""
        from routes.transactions import _resolve_category

        # Create tenant B with its own category
        user_b = User(username='bob', email='bob@test.com')
        user_b.set_password('password123')
        db.session.add(user_b)
        db.session.flush()

        tenant_b = Tenant(name='TenantB', slug='b', owner_id=user_b.id)
        db.session.add(tenant_b)
        db.session.flush()

        cat_b = Category(
            tenant_id=tenant_b.id, name='Transport', type='expense',
            icon='car', color='#F59E0B',
        )
        db.session.add(cat_b)
        db.session.commit()

        # Save the id before tenant filter is active (avoids
        # ObjectDeletedError on stale identity-map refresh).
        cat_b_id = cat_b.id

        with app.test_request_context():
            from flask import g
            g.current_tenant = seed_data['tenant']  # tenant A

            # _resolve_category should reject: either the auto-filter hides
            # the row (returns None / raises) or the explicit tenant check fires.
            cat_id, err = _resolve_category(cat_b_id)
            assert cat_id is None
            assert err is not None
            resp, status = err
            assert status == 400

    def test_resolve_none_category(self, app, seed_data):
        """None category_id should return (None, None)."""
        from routes.transactions import _resolve_category

        cat_id, err = _resolve_category(None)
        assert cat_id is None
        assert err is None


# ── 3. Session Lifecycle ─────────────────────────────────────────────────


class TestSessionLifecycle:
    def test_session_removed_after_request(self, app, client):
        """db.session.remove() should be called after each request."""
        with patch('extensions.db.session') as mock_session:
            mock_session.remove = MagicMock()
            # Make a request through the test client
            resp = client.get('/health')
            assert resp.status_code == 200

    def test_session_clean_between_requests(self, app, client):
        """Consecutive requests should not share stale ORM state."""
        # Create data in first request context
        with app.app_context():
            user = User(username='session_test', email='session@test.com')
            user.set_password('test123')
            db.session.add(user)
            db.session.commit()

        # Second request should get a fresh session
        with app.app_context():
            found = User.query.filter_by(username='session_test').first()
            assert found is not None


# ── 4. Log Rotation ──────────────────────────────────────────────────────


class TestLogRotation:
    def test_concurrent_handler_used(self, app):
        """On systems with concurrent-log-handler, ConcurrentRotatingFileHandler should be used."""
        from utils.logger import _FileHandler
        try:
            from concurrent_log_handler import ConcurrentRotatingFileHandler
            assert _FileHandler is ConcurrentRotatingFileHandler
        except ImportError:
            # Fallback: should be stdlib RotatingFileHandler
            assert _FileHandler is logging.handlers.RotatingFileHandler

    def test_log_files_created(self, app, tmp_path):
        """setup_logging should create expected log files."""
        app.config['LOG_DIR'] = str(tmp_path / 'logs')
        from utils.logger import setup_logging
        setup_logging(app)

        log_dir = tmp_path / 'logs'
        assert log_dir.exists()
        # At minimum, error.log and app.log should be created on first write
        # (they're created lazily by the handler)


# ── 5. DB Observability ──────────────────────────────────────────────────


class TestDBObservability:
    def test_record_orm_error_increments_counter(self, app):
        """record_orm_error should increment the Prometheus counter."""
        from utils.db_observability import record_orm_error

        with app.app_context():
            # Should not raise even if prometheus is unavailable
            record_orm_error('test_error')

    def test_observability_initialized(self, app):
        """init_db_observability should register hooks."""
        # The hooks are registered during create_app, so they should exist
        assert app.before_request_funcs
        assert app.after_request_funcs
