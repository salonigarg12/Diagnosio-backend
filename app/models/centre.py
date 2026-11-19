from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Centre(Base):
    """Diagnostic centre owned by a single CENTRE_ADMIN user."""

    __tablename__ = "centres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    opening_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    closing_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=17)
    max_capacity_per_slot: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    owner = relationship("User", back_populates="centre")
    centre_tests = relationship(
        "CentreTest",
        back_populates="centre",
        cascade="all, delete-orphan",
    )
    bookings = relationship("Booking", back_populates="centre")


class Test(Base):
    """Master catalogue entry for a diagnostic test (e.g., CBC, Lipid Profile)."""

    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    centre_tests = relationship("CentreTest", back_populates="test")


class CentreTest(Base):
    """Pricing and availability mapping between a Centre and a Test."""

    __tablename__ = "centre_tests"
    __table_args__ = (
        UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    centre_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    centre = relationship("Centre", back_populates="centre_tests")
    test = relationship("Test", back_populates="centre_tests")
    booking_items = relationship("BookingItem", back_populates="centre_test")
