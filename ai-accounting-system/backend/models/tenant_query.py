"""SQLAlchemy query filter that automatically enforces tenant isolation.

This is the defense-in-depth layer: even if a route forgets to filter by tenant_id,
the ORM will inject the filter automatically when g.current_tenant is set.

Models opt in by having a `tenant_id` column.  Models without tenant_id are
considered global (e.g. Plan, Role, Permission) and are not filtered.
"""

import logging
from sqlalchemy import event
from flask import g

logger = logging.getLogger(__name__)

# Models that should be exempt from auto-filtering even though they have tenant_id.
_EXEMPT_MODELS = set()


def setup_tenant_query_filter():
    """Install the do_orm_execute event listener on Session.

    Call this once inside create_app() after db.init_app(app).
    """
    from extensions import db

    @event.listens_for(db.Session, 'do_orm_execute')
    def _do_orm_execute(orm_execute_state):
        """Inject tenant_id filter into SELECT queries for models with tenant_id column."""
        # Only intercept bulk SELECT statements
        if not orm_execute_state.is_select:
            return

        # Only apply when there is an active request with a tenant
        tenant = getattr(g, 'current_tenant', None)
        if tenant is None:
            return

        # Get the primary mapper/entity being queried
        # For simple queries, we can check the statement's columns
        stmt = orm_execute_state.statement

        # Try to find the primary entity (model class) from the statement
        # This handles: Model.query, db.session.query(Model), db.select(Model)
        from sqlalchemy import inspect as sa_inspect
        from sqlalchemy.orm import Mapper

        primary_entity = None
        if hasattr(stmt, 'column_descriptions'):
            for desc in stmt.column_descriptions:
                entity = desc.get('entity')
                if entity and hasattr(entity, 'tenant_id') and entity not in _EXEMPT_MODELS:
                    primary_entity = entity
                    break

        if primary_entity is None:
            return

        # Check if the query already has a tenant_id filter to avoid double-filtering
        # We do this by checking the statement's where clause for tenant_id references
        stmt_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        if 'tenant_id' in stmt_str and f'tenant_id = {tenant.id}' in stmt_str:
            return

        # Inject the filter
        orm_execute_state.statement = stmt.where(
            primary_entity.tenant_id == tenant.id
        )
