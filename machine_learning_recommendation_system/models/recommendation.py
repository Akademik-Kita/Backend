from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import JSON_TYPE, Base, IdMixin, utcnow


class RecommendationRun(IdMixin, Base):
    __tablename__ = "recommendation_runs"
    student_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE")
    )
    target_type: Mapped[str] = mapped_column(String(20), default="sekolah")
    model_version: Mapped[str] = mapped_column(String(50))
    input_snapshot: Mapped[dict] = mapped_column(JSON_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items: Mapped[list["RecommendationItem"]] = relationship(
        cascade="all, delete-orphan", order_by="RecommendationItem.rank", lazy="raise"
    )
    __table_args__ = (
        Index("ix_recommendation_runs_student_created", "student_profile_id", "created_at"),
    )


class RecommendationItem(IdMixin, Base):
    __tablename__ = "recommendation_items"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("recommendation_runs.id", ondelete="CASCADE"))
    program_id: Mapped[UUID] = mapped_column(ForeignKey("programs.id"))
    rank: Mapped[int] = mapped_column(Integer)
    total_score: Mapped[float] = mapped_column(Float)
    score_breakdown: Mapped[dict] = mapped_column(JSON_TYPE)
    chance_low: Mapped[float] = mapped_column(Float)
    chance_high: Mapped[float] = mapped_column(Float)
    explanation: Mapped[dict] = mapped_column(JSON_TYPE)
    category: Mapped[str] = mapped_column(String(20))
    __table_args__ = (
        UniqueConstraint("run_id", "rank"),
        UniqueConstraint("run_id", "program_id"),
        CheckConstraint("total_score BETWEEN 0 AND 100"),
        CheckConstraint("chance_low >= 0 AND chance_low <= chance_high AND chance_high <= 100"),
        CheckConstraint("category IN ('ambisius','realistis','aman')"),
    )
