from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SQLEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import UserRole
from app.database import Base


class User(Base):
    """Application user account supporting PATIENT and CENTRE_ADMIN roles."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.PATIENT,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    centre = relationship("Centre", back_populates="owner", uselist=False)
    bookings = relationship("Booking", back_populates="user")
