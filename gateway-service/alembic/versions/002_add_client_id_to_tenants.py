"""add client_id to tenants for platform-domain sync

Revision ID: 002
Revises: 001
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("client_id", sa.UUID(), nullable=True),
    )
    op.create_index("ix_tenants_client_id", "tenants", ["client_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenants_client_id", table_name="tenants")
    op.drop_column("tenants", "client_id")
