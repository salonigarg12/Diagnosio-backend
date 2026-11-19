from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import PaymentStatus
from app.database import Base


class Payment(Base):
    """Payment record linked one-to-one with a Booking."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bookings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus, name="payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    transaction_ref: Mapped[str | None] = mapped_column(
        String(120),
        unique=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    booking = relationship("Booking", back_populates="payment")


class WebhookEvent(Base):
    """Audit log enforcing payment webhook idempotency via unique event_id."""

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    booking_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    booking = relationship("Booking", back_populates="webhook_events")
