"""SQLAlchemy models for users and authentication-check summaries."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class AccountType(StrEnum):
    """Supported eMaktab account categories."""

    STUDENT = "student"
    PARENT = "parent"


class CheckStatus(StrEnum):
    """Possible outcomes of an authentication check."""

    SUCCESS = "success"
    INVALID_CREDENTIALS = "invalid_credentials"
    UNKNOWN = "unknown"


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class User(Base):
    """Authorized Telegram user who owns check reports."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("telegram_id", name="uq_users_telegram_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    check_batches: Mapped[list["CheckBatch"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class CheckBatch(Base):
    """Aggregate counts for one authentication-check report."""

    __tablename__ = "check_batches"
    __table_args__ = (
        CheckConstraint(
            "total_count >= 0 AND success_count >= 0 AND "
            "invalid_count >= 0 AND unknown_count >= 0 AND "
            "total_count = success_count + invalid_count + unknown_count",
            name="ck_check_batches_counts",
        ),
        Index("ix_check_batches_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unknown_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    user: Mapped[User] = relationship(back_populates="check_batches")
    check_results: Mapped[list["CheckResult"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class CheckResult(Base):
    """Credential-free record of one authentication-check outcome."""

    __tablename__ = "check_results"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('student', 'parent')",
            name="ck_check_results_account_type",
        ),
        CheckConstraint(
            "status IN ('success', 'invalid_credentials', 'unknown')",
            name="ck_check_results_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("check_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_label: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    batch: Mapped[CheckBatch] = relationship(back_populates="check_results")
