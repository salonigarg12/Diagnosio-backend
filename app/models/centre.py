from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

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