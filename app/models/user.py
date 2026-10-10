from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Date, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Identity
    first_name: Mapped[str]    = mapped_column(String(100))
    last_name:  Mapped[str]    = mapped_column(String(100))
    username:   Mapped[str]    = mapped_column(String(30), unique=True, index=True)

    # Contact
    email:      Mapped[str]    = mapped_column(String(254), unique=True, index=True)
    phone:      Mapped[str]    = mapped_column(String(30))

    # Auth
    hashed_password: Mapped[str] = mapped_column(String(255))
    auth_provider: Mapped[str] = mapped_column(String(16), default="password", nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Profile
    date_of_birth:      Mapped[str | None] = mapped_column(String(20),  nullable=True)
    relationship_status: Mapped[str | None] = mapped_column(String(50),  nullable=True)
    location:            Mapped[str | None] = mapped_column(String(100), nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Grapsy Python course progress
    learning_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    code_submission_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_review_result: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    terms_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
