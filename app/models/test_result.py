from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    input: Mapped[str] = mapped_column(String, nullable=False)
    output: Mapped[str] = mapped_column(String, nullable=False, default="")
    test_type: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    judge_scores: Mapped[list | None] = mapped_column(JSON, nullable=True)
    judge_agreement: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    execution_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_source: Mapped[str] = mapped_column(String, nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
