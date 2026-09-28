from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import List, Optional
from app.constants.enums import BookingStatus, PaymentStatus

# Auth Schemas
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

# Centre & Catalogue Schemas
class TestResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    model_config = ConfigDict(from_attributes=True)

class CentreResponse(BaseModel):
    id: int
    name: str
    location: str
    model_config = ConfigDict(from_attributes=True)

class CentreDetailResponse(CentreResponse):
    tests: List[TestResponse] = []

# Booking Schemas (Multi-Test Support)
class BookingCreate(BaseModel):
    centre_id: int
    test_ids: List[int]
    appointment_time: datetime

class BookingItemResponse(BaseModel):
    test_id: int
    price_at_booking: float
    model_config = ConfigDict(from_attributes=True)

class BookingResponse(BaseModel):
    id: int
    user_id: int
    centre_id: int
    total_amount: float
    status: str
    appointment_time: datetime
    items: List[BookingItemResponse] = []
    model_config = ConfigDict(from_attributes=True)

class BookingStatusUpdate(BaseModel):
    status: BookingStatus

# Payment & Webhook Schemas
class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    amount: float
    status: str
    model_config = ConfigDict(from_attributes=True)

class WebhookPayload(BaseModel):
    event_id: str
    booking_id: int
    status: str