from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.constants.enums import BookingStatus, PaymentStatus, UserRole


# ---------------------------------------------------------------------------
# Auth & User Schemas
# ---------------------------------------------------------------------------


class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    role: UserRole = Field(default=UserRole.PATIENT)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    full_name: str
    email: EmailStr
    role: UserRole


# ---------------------------------------------------------------------------
# Centre & Diagnostic Test Schemas
# ---------------------------------------------------------------------------


class CentreCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    city: str = Field(..., min_length=2, max_length=100)
    address: str = Field(..., min_length=5, max_length=300)
    opening_hour: int = Field(default=9, ge=0, le=23)
    closing_hour: int = Field(default=17, ge=1, le=24)
    max_capacity_per_slot: int = Field(default=1, ge=1, le=500)

    @model_validator(mode="after")
    def validate_operating_hours(self) -> "CentreCreateRequest":
        if self.closing_hour <= self.opening_hour:
            raise ValueError("closing_hour must be strictly greater than opening_hour.")
        return self


class CentreTestUpsertRequest(BaseModel):
    test_name: str = Field(..., min_length=2, max_length=150)
    description: str = Field(default="", max_length=500)
    price: Decimal = Field(..., gt=0)
    is_available: bool = Field(default=True)

    @field_validator("test_name")
    @classmethod
    def clean_test_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("test_name must be at least 2 characters.")
        return cleaned


class CentreTestResponse(BaseModel):
    centre_test_id: int
    test_id: int
    test_name: str
    description: str
    price: Decimal
    is_available: bool


class CentreResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    city: str
    address: str
    opening_hour: int
    closing_hour: int
    max_capacity_per_slot: int
    created_at: datetime
    tests: List[CentreTestResponse] = Field(default_factory=list)


class SlotAvailabilityResponse(BaseModel):
    slot_time: datetime
    label: str
    booked_count: int
    max_capacity: int
    available_spots: int
    is_available: bool


# ---------------------------------------------------------------------------
# Booking Schemas
# ---------------------------------------------------------------------------


class BookingCreateRequest(BaseModel):
    centre_id: int = Field(..., gt=0)
    centre_test_ids: List[int] = Field(..., min_length=1)
    appointment_time: datetime

    @field_validator("centre_test_ids")
    @classmethod
    def deduplicate_test_ids(cls, value: List[int]) -> List[int]:
        unique_ids = list(dict.fromkeys(value))
        if not unique_ids:
            raise ValueError("At least one diagnostic test must be selected.")
        return unique_ids

    @field_validator("appointment_time")
    @classmethod
    def normalize_hourly_slot(cls, value: datetime) -> datetime:
        naive_dt = value.replace(tzinfo=None)
        if naive_dt.minute != 0 or naive_dt.second != 0 or naive_dt.microsecond != 0:
            raise ValueError(
                "appointment_time must align to a fixed 1-hour slot (e.g., 10:00:00)."
            )
        return naive_dt


class BookingItemResponse(BaseModel):
    id: int
    centre_test_id: int
    test_name_snapshot: str
    price_snapshot: Decimal


class BookingResponse(BaseModel):
    id: int
    user_id: int
    patient_name: str
    patient_email: EmailStr
    centre_id: int
    centre_name: str
    centre_city: str
    appointment_time: datetime
    total_amount: Decimal
    status: BookingStatus
    payment_status: PaymentStatus
    created_at: datetime
    items: List[BookingItemResponse] = Field(default_factory=list)


class CentreStatsResponse(BaseModel):
    total_bookings: int
    pending_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    offered_tests_count: int


class CentreAdminDashboardResponse(BaseModel):
    centre: CentreResponse
    stats: CentreStatsResponse
    bookings: List[BookingResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Payment Webhook Schemas
# ---------------------------------------------------------------------------


class PaymentWebhookRequest(BaseModel):
    event_id: str = Field(..., min_length=3, max_length=120)
    booking_id: int = Field(..., gt=0)
    status: PaymentStatus = Field(default=PaymentStatus.SUCCESS)
    transaction_ref: Optional[str] = Field(default=None, max_length=120)


class PaymentWebhookResponse(BaseModel):
    event_id: str
    booking_id: int
    booking_status: BookingStatus
    payment_status: PaymentStatus
    idempotent_replay: bool
    message: str
