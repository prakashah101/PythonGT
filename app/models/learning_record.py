from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LearningRecord(Base):
    __tablename__ = "learning_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_answer: Mapped[str] = mapped_column(Text, nullable=False)
    teacher_feedback: Mapped[str] = mapped_column(Text, default="", nullable=False)
    result: Mapped[str] = mapped_column(String(12), nullable=False)
    accuracy_score: Mapped[int] = mapped_column(Integer, nullable=False)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    learning_level: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    topic_id: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
