from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.constants.enums import BookingStatus, PaymentStatus

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="user")

class Centre(Base):
    __tablename__ = "centres"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    location = Column(String(255), nullable=False)

    centre_tests = relationship("CentreTest", back_populates="centre")
    bookings = relationship("Booking", back_populates="centre")

class Test(Base):
    __tablename__ = "tests"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)

    centre_tests = relationship("CentreTest", back_populates="test")

class CentreTest(Base):
    __tablename__ = "centre_tests"
    id = Column(Integer, primary_key=True, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    price = Column(Float, nullable=False)

    centre = relationship("Centre", back_populates="centre_tests")
    test = relationship("Test", back_populates="centre_tests")

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    centre_id = Column(Integer, ForeignKey("centres.id"), nullable=False)
    appointment_time = Column(DateTime, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(50), default=BookingStatus.PENDING.value, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

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

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(50), default=PaymentStatus.PENDING.value, nullable=False)
    transaction_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    booking = relationship("Booking", back_populates="payments")

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), unique=True, index=True, nullable=False)
    booking_id = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow)