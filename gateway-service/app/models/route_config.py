import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class RouteConfig(Base):
    __tablename__ = "route_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path_prefix: Mapped[str] = mapped_column(String(512), nullable=False)
    methods: Mapped[list] = mapped_column(
        JSON, default=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    )
    strip_prefix: Mapped[bool] = mapped_column(Boolean, default=False)
    prefix_rewrite: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=30000)
    retry_attempts: Mapped[int] = mapped_column(Integer, default=3)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    headers_to_add: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    application: Mapped["Application"] = relationship("Application", back_populates="route_configs")
