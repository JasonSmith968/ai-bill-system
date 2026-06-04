"""add multi-tenant architecture

Revision ID: a1b2c3d4e5f6
Revises: 3249f33596ac
Create Date: 2026-05-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '3249f33596ac'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(50), nullable=False, unique=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('plans.id'), nullable=True),
        sa.Column('stripe_customer_id', sa.String(200), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(200), nullable=True),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('max_members', sa.Integer(), server_default='5'),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'], unique=True)

    # 2. Create tenant_members table
    op.create_table(
        'tenant_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='member'),
        sa.Column('joined_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_user'),
    )
    op.create_index('ix_tenant_members_tenant_id', 'tenant_members', ['tenant_id'])
    op.create_index('ix_tenant_members_user_id', 'tenant_members', ['user_id'])

    # 3. Add tenant_id to all business tables (nullable first for data migration)
    tables_to_migrate = [
        'users', 'transactions', 'categories', 'subscriptions', 'usage_logs',
        'agent_execution_logs', 'agent_memories', 'task_records', 'audit_logs',
        'encrypted_credentials', 'prompt_templates',
    ]

    for table in tables_to_migrate:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=True))
            batch_op.create_index(f'ix_{table}_tenant_id', ['tenant_id'])

    # 4. Add FK constraints
    for table in tables_to_migrate:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_foreign_key(
                f'fk_{table}_tenant_id', 'tenants', ['tenant_id'], ['id']
            )

    # 5. Data migration: create default tenant and assign existing data
    op.execute("""
        INSERT INTO tenants (name, slug, status, max_members, created_at, updated_at)
        VALUES ('Default Workspace', 'default', 'active', 999, NOW(), NOW())
    """)

    # Get the default tenant ID
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM tenants WHERE slug = 'default'"))
    default_tenant_id = result.fetchone()[0]

    # Set all existing users' tenant_id
    op.execute(sa.text(f"UPDATE users SET tenant_id = {default_tenant_id} WHERE tenant_id IS NULL"))

    # Set all owner users as tenant members
    op.execute(sa.text(f"""
        INSERT INTO tenant_members (tenant_id, user_id, role, joined_at)
        SELECT {default_tenant_id}, id, CASE WHEN is_admin THEN 'owner' ELSE 'member' END, NOW()
        FROM users
        WHERE id NOT IN (SELECT user_id FROM tenant_members WHERE tenant_id = {default_tenant_id})
    """))

    # Update tenant owner
    op.execute(sa.text(f"""
        UPDATE tenants SET owner_id = (
            SELECT id FROM users WHERE is_admin = 1 LIMIT 1
        ) WHERE id = {default_tenant_id}
    """))

    # Set tenant_id on other tables
    for table in ['transactions', 'categories', 'subscriptions', 'usage_logs',
                   'agent_execution_logs', 'agent_memories', 'task_records',
                   'audit_logs', 'encrypted_credentials', 'prompt_templates']:
        if table == 'categories':
            # Categories may be global (NULL tenant) — only set for user-bound ones
            op.execute(sa.text(f"""
                UPDATE {table} SET tenant_id = {default_tenant_id}
                WHERE tenant_id IS NULL AND id IN (
                    SELECT DISTINCT category_id FROM transactions WHERE category_id IS NOT NULL
                )
            """))
            op.execute(sa.text(f"""
                UPDATE {table} SET tenant_id = {default_tenant_id}
                WHERE tenant_id IS NULL AND is_default = 1
            """))
        elif table == 'subscriptions':
            op.execute(sa.text(f"""
                UPDATE {table} SET tenant_id = {default_tenant_id}
                WHERE tenant_id IS NULL AND user_id IS NOT NULL
            """))
        elif table in ('audit_logs', 'encrypted_credentials'):
            # These may have NULL user_id
            op.execute(sa.text(f"UPDATE {table} SET tenant_id = {default_tenant_id} WHERE tenant_id IS NULL"))
        else:
            op.execute(sa.text(f"UPDATE {table} SET tenant_id = {default_tenant_id} WHERE tenant_id IS NULL"))

    # 6. Make tenant_id NOT NULL for core tables
    for table in ['transactions']:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('tenant_id', nullable=False)


def downgrade():
    # Drop tenant_id columns
    tables = [
        'users', 'transactions', 'categories', 'subscriptions', 'usage_logs',
        'agent_execution_logs', 'agent_memories', 'task_records', 'audit_logs',
        'encrypted_credentials', 'prompt_templates',
    ]

    for table in tables:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f'fk_{table}_tenant_id', type_='foreignkey')
            batch_op.drop_index(f'ix_{table}_tenant_id')
            batch_op.drop_column('tenant_id')

    # Drop tenant_members and tenants
    op.drop_index('ix_tenant_members_user_id', table_name='tenant_members')
    op.drop_index('ix_tenant_members_tenant_id', table_name='tenant_members')
    op.drop_table('tenant_members')
    op.drop_index('ix_tenants_slug', table_name='tenants')
    op.drop_table('tenants')
