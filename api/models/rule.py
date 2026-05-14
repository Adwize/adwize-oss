import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Enum, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.base import Base


class RuleType(str, enum.Enum):
    THRESHOLD = "THRESHOLD"
    FIELD_VALIDATION = "FIELD_VALIDATION"
    VOLUME = "VOLUME"


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (Index("ix_rules_active", "is_active"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType, native_enum=False), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tag: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Rule(id={self.id}, name={self.name}, type={self.rule_type})>"
