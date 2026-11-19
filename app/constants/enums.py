from enum import Enum


class UserRole(str, Enum):
    """Supported application user roles for Role-Based Access Control (RBAC)."""

    PATIENT = "PATIENT"
    CENTRE_ADMIN = "CENTRE_ADMIN"


class BookingStatus(str, Enum):
    """Lifecycle states of a diagnostic appointment booking."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, Enum):
    """Lifecycle states of a booking payment record."""

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
