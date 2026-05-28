import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all, delete")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
        }


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    exchange: Mapped[str] = mapped_column(String(50))
    api_key_enc: Mapped[bytes] = mapped_column(LargeBinary)
    api_secret_enc: Mapped[bytes] = mapped_column(LargeBinary)
    passphrase_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)
    is_paper: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="api_keys")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "exchange": self.exchange,
            "is_paper": self.is_paper,
            "created_at": self.created_at.isoformat(),
        }
