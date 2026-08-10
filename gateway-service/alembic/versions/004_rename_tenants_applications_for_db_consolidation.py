"""rename tenants/applications to gateway_tenants/gateway_applications

All repos now share a single Postgres server/database (clan_platform on
port 5432) instead of one database per service. platform-domain-be
(admin-service) already owns tables named "tenants" and "applications"
with unrelated schemas, so the gateway's local mirror tables are renamed
to avoid colliding once both live in the same database.

Revision ID: 004
Revises: 003
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("tenants", "gateway_tenants")
    op.rename_table("applications", "gateway_applications")

    op.execute("ALTER INDEX IF EXISTS ix_tenants_slug RENAME TO ix_gateway_tenants_slug")
    op.execute("ALTER INDEX IF EXISTS ix_tenants_is_active RENAME TO ix_gateway_tenants_is_active")
    op.execute("ALTER INDEX IF EXISTS ix_tenants_admin_tenant_id RENAME TO ix_gateway_tenants_admin_tenant_id")
    op.execute("ALTER INDEX IF EXISTS ix_applications_tenant_id RENAME TO ix_gateway_applications_tenant_id")
    op.execute("ALTER INDEX IF EXISTS ix_applications_is_active RENAME TO ix_gateway_applications_is_active")


def downgrade() -> None:
    op.execute("ALTER INDEX IF EXISTS ix_gateway_tenants_slug RENAME TO ix_tenants_slug")
    op.execute("ALTER INDEX IF EXISTS ix_gateway_tenants_is_active RENAME TO ix_tenants_is_active")
    op.execute("ALTER INDEX IF EXISTS ix_gateway_tenants_admin_tenant_id RENAME TO ix_tenants_admin_tenant_id")
    op.execute("ALTER INDEX IF EXISTS ix_gateway_applications_tenant_id RENAME TO ix_applications_tenant_id")
    op.execute("ALTER INDEX IF EXISTS ix_gateway_applications_is_active RENAME TO ix_applications_is_active")

    op.rename_table("gateway_tenants", "tenants")
    op.rename_table("gateway_applications", "applications")
