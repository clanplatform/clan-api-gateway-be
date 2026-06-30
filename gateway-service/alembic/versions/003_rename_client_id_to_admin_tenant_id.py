"""rename client_id to admin_tenant_id in tenants table

Revision ID: 003
Revises: 002
Create Date: 2026-06-30

Renames the cross-service reference column from client_id (old name from when
platform-domain-be called them "clients") to admin_tenant_id (matches the
current tenants.tenant_id column in platform-domain-be).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename index first (must drop before renaming column on some PG versions)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'tenants' AND indexname = 'ix_tenants_client_id'
            ) THEN
                ALTER INDEX ix_tenants_client_id RENAME TO ix_tenants_admin_tenant_id;
            END IF;
        END $$;
    """)

    # Rename column
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'client_id'
            ) THEN
                ALTER TABLE tenants RENAME COLUMN client_id TO admin_tenant_id;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'admin_tenant_id'
            ) THEN
                ALTER TABLE tenants RENAME COLUMN admin_tenant_id TO client_id;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'tenants' AND indexname = 'ix_tenants_admin_tenant_id'
            ) THEN
                ALTER INDEX ix_tenants_admin_tenant_id RENAME TO ix_tenants_client_id;
            END IF;
        END $$;
    """)
