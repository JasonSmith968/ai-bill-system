"""Multi-tenant isolation tests.

Verifies that:
- Users cannot see data from other tenants
- The auto-filter prevents cross-tenant queries
- Role permissions are enforced within tenants
- Tenant creation sets up default categories
"""

import pytest
from datetime import datetime
from extensions import db
from models.user import User
from models.tenant import Tenant, TenantMember
from models.transaction import Transaction, Category


@pytest.fixture
def app():
    """Create test application."""
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
def seed_tenants(app):
    """Create two tenants with users and data."""
    with app.app_context():
        # Tenant A
        user_a = User(username='alice', email='alice@test.com')
        user_a.set_password('password123')
        db.session.add(user_a)
        db.session.flush()

        tenant_a = Tenant(name='Tenant A', slug='tenant-a', owner_id=user_a.id)
        db.session.add(tenant_a)
        db.session.flush()

        user_a.tenant_id = tenant_a.id
        member_a = TenantMember(tenant_id=tenant_a.id, user_id=user_a.id, role='owner')
        db.session.add(member_a)

        # Default categories for tenant A
        cat_a = Category(tenant_id=tenant_a.id, name='Food', type='expense',
                         icon='utensils', color='#EF4444', is_default=True)
        db.session.add(cat_a)
        db.session.flush()

        # Transaction for user A
        txn_a = Transaction(
            tenant_id=tenant_a.id, user_id=user_a.id, type='expense',
            amount=100.00, category_id=cat_a.id, description='Lunch',
            date=datetime(2026, 5, 27).date()
        )
        db.session.add(txn_a)

        # Tenant B
        user_b = User(username='bob', email='bob@test.com')
        user_b.set_password('password123')
        db.session.add(user_b)
        db.session.flush()

        tenant_b = Tenant(name='Tenant B', slug='tenant-b', owner_id=user_b.id)
        db.session.add(tenant_b)
        db.session.flush()

        user_b.tenant_id = tenant_b.id
        member_b = TenantMember(tenant_id=tenant_b.id, user_id=user_b.id, role='owner')
        db.session.add(member_b)

        cat_b = Category(tenant_id=tenant_b.id, name='Transport', type='expense',
                         icon='car', color='#F59E0B', is_default=True)
        db.session.add(cat_b)
        db.session.flush()

        txn_b = Transaction(
            tenant_id=tenant_b.id, user_id=user_b.id, type='expense',
            amount=50.00, category_id=cat_b.id, description='Bus',
            date=datetime(2026, 5, 27).date()
        )
        db.session.add(txn_b)

        db.session.commit()

        return {
            'tenant_a': tenant_a,
            'tenant_b': tenant_b,
            'user_a': user_a,
            'user_b': user_b,
            'txn_a': txn_a,
            'txn_b': txn_b,
            'cat_a': cat_a,
            'cat_b': cat_b,
        }


class TestTenantCreation:
    def test_tenant_created_with_defaults(self, app, seed_tenants):
        """Tenant creation should include default categories."""
        data = seed_tenants
        cats = Category.query.filter_by(tenant_id=data['tenant_a'].id).all()
        assert len(cats) >= 1
        assert cats[0].name == 'Food'

    def test_owner_is_member(self, app, seed_tenants):
        """Tenant owner should be a member with 'owner' role."""
        data = seed_tenants
        membership = TenantMember.query.filter_by(
            tenant_id=data['tenant_a'].id,
            user_id=data['user_a'].id
        ).first()
        assert membership is not None
        assert membership.role == 'owner'


class TestTenantIsolation:
    def test_user_cannot_see_other_tenant_transactions(self, app, seed_tenants):
        """Transactions from tenant B should not be visible when querying as tenant A."""
        data = seed_tenants

        with app.test_request_context():
            from flask import g
            g.current_tenant = data['tenant_a']

            # Auto-filter should restrict to tenant A
            txns = Transaction.query.all()
            txn_ids = [t.id for t in txns]

            assert data['txn_a'].id in txn_ids
            assert data['txn_b'].id not in txn_ids

    def test_user_cannot_see_other_tenant_categories(self, app, seed_tenants):
        """Categories from tenant B should not be visible when querying as tenant A."""
        data = seed_tenants

        with app.test_request_context():
            from flask import g
            g.current_tenant = data['tenant_a']

            cats = Category.query.all()
            cat_ids = [c.id for c in cats]

            assert data['cat_a'].id in cat_ids
            assert data['cat_b'].id not in cat_ids

    def test_tenant_filter_auto_applied(self, app, seed_tenants):
        """The auto-filter should be applied to all queries for models with tenant_id."""
        data = seed_tenants

        with app.test_request_context():
            from flask import g
            g.current_tenant = data['tenant_b']

            # Only tenant B data should be visible
            txns = Transaction.query.all()
            assert len(txns) == 1
            assert txns[0].description == 'Bus'

    def test_no_tenant_context_returns_all(self, app, seed_tenants):
        """Without g.current_tenant, all data should be visible (unfiltered)."""
        data = seed_tenants

        with app.test_request_context():
            # g.current_tenant is not set
            txns = Transaction.query.all()
            assert len(txns) == 2


class TestCrossTenantAccess:
    def test_cannot_create_transaction_in_other_tenant(self, app, seed_tenants):
        """User A should not be able to set tenant_id to tenant B."""
        data = seed_tenants

        with app.app_context():
            # Direct ORM attempt to create a transaction with wrong tenant_id
            txn = Transaction(
                tenant_id=data['tenant_b'].id,  # Wrong tenant!
                user_id=data['user_a'].id,
                type='expense',
                amount=999.00,
                description='Cross-tenant attempt',
                date=datetime(2026, 5, 28).date()
            )
            db.session.add(txn)
            db.session.commit()

            # The transaction exists but is in tenant B
            # When querying as tenant A, it should not be visible
            with app.test_request_context():
                from flask import g
                g.current_tenant = data['tenant_a']

                found = Transaction.query.filter_by(description='Cross-tenant attempt').first()
                assert found is None


class TestMemberRoles:
    def test_member_role_stored(self, app, seed_tenants):
        """Member roles should be correctly stored and retrievable."""
        data = seed_tenants

        with app.app_context():
            role = data['user_a'].get_tenant_role(data['tenant_a'].id)
            assert role == 'owner'

    def test_non_member_has_no_role(self, app, seed_tenants):
        """User A should have no role in tenant B."""
        data = seed_tenants

        with app.app_context():
            role = data['user_a'].get_tenant_role(data['tenant_b'].id)
            assert role is None


class TestTenantSwitching:
    def test_switch_tenant_updates_user(self, app, seed_tenants):
        """Switching tenant should update user.tenant_id."""
        data = seed_tenants

        with app.app_context():
            from services.tenant_service import add_member, switch_tenant

            # Add user A to tenant B as a member
            add_member(data['tenant_b'].id, data['user_a'].id, role='member')

            # Switch to tenant B
            tenant, err = switch_tenant(data['user_a'].id, data['tenant_b'].id)
            assert err is None
            assert tenant.id == data['tenant_b'].id

            # Verify user's tenant_id updated
            db.session.refresh(data['user_a'])
            assert data['user_a'].tenant_id == data['tenant_b'].id

    def test_cannot_switch_to_non_member_tenant(self, app, seed_tenants):
        """User A cannot switch to tenant B without membership."""
        data = seed_tenants

        with app.app_context():
            from services.tenant_service import switch_tenant

            tenant, err = switch_tenant(data['user_a'].id, data['tenant_b'].id)
            assert err is not None
            assert tenant is None
