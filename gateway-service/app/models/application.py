import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, JSON, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Application(Base):
    __tablename__ = "gateway_applications"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_app_tenant_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gateway_tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    upstream_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    upstream_host: Mapped[str] = mapped_column(String(255), nullable=False)
    upstream_port: Mapped[int] = mapped_column(Integer, default=80)
    upstream_tls: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_limit_rps: Mapped[int] = mapped_column(Integer, default=100)
    rate_limit_burst: Mapped[int] = mapped_column(Integer, default=200)
    cors_origins: Mapped[list] = mapped_column(JSON, default=list)
    jwt_required: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="applications")
    route_configs: Mapped[list["RouteConfig"]] = relationship(
        "RouteConfig", back_populates="application", lazy="selectin", cascade="all, delete-orphan"
    )
