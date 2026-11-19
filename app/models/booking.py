from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import BookingStatus
from app.database import Base


class Booking(Base):
    """Diagnostic appointment booking supporting multiple diagnostic tests via BookingItem."""

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    centre_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus, name="booking_status"),
        nullable=False,
        default=BookingStatus.PENDING,
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

    user = relationship("User", back_populates="bookings")
    centre = relationship("Centre", back_populates="bookings")
    items = relationship(
        "BookingItem",
        back_populates="booking",
        cascade="all, delete-orphan",
    )
    payment = relationship(
        "Payment",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
    )
    webhook_events = relationship("WebhookEvent", back_populates="booking")


class BookingItem(Base):
    """Line item storing a price and name snapshot for each test included in a booking."""

    __tablename__ = "booking_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    centre_test_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("centre_tests.id", ondelete="RESTRICT"),
        nullable=False,
    )
    test_name_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    booking = relationship("Booking", back_populates="items")
    centre_test = relationship("CentreTest", back_populates="booking_items")
