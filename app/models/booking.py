from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from app.constants.enums import BookingStatus

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    centre_id = Column(Integer, ForeignKey("centres.id"), nullable=False)
    appointment_time = Column(DateTime, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(50), default=BookingStatus.PENDING.value, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="bookings")
    centre = relationship("Centre", back_populates="bookings")
    items = relationship("BookingItem", back_populates="booking", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="booking")


class BookingItem(Base):
    __tablename__ = "booking_items"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    price_at_booking = Column(Float, nullable=False)

    booking = relationship("Booking", back_populates="items")
    test = relationship("Test")