"""initial tables: tenants, applications, route_configs

Revision ID: 001
Revises:
Create Date: 2026-06-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tenants ──────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="starter"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_is_active", "tenants", ["is_active"])

    # ── applications ─────────────────────────────────────────────────────────
    op.create_table(
        "applications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("upstream_url", sa.String(2048), nullable=False),
        sa.Column("upstream_host", sa.String(255), nullable=False),
        sa.Column("upstream_port", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("upstream_tls", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rate_limit_rps", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("rate_limit_burst", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("cors_origins", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("jwt_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_app_tenant_slug"),
    )
    op.create_index("ix_applications_tenant_id", "applications", ["tenant_id"])
    op.create_index("ix_applications_is_active", "applications", ["is_active"])

    # ── route_configs ─────────────────────────────────────────────────────────
    op.create_table(
        "route_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("path_prefix", sa.String(512), nullable=False),
        sa.Column(
            "methods",
            sa.JSON(),
            nullable=False,
            server_default='["GET","POST","PUT","DELETE","PATCH","OPTIONS"]',
        ),
        sa.Column("strip_prefix", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("prefix_rewrite", sa.String(512), nullable=True),
        sa.Column("timeout_ms", sa.Integer(), nullable=False, server_default="30000"),
        sa.Column("retry_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("headers_to_add", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_route_configs_application_id", "route_configs", ["application_id"]
    )


def downgrade() -> None:
    op.drop_table("route_configs")
    op.drop_table("applications")
    op.drop_table("tenants")
