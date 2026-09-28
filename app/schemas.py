from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from app.models import BookingStatus

# User Schemas
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# Diagnostic Test & Centre Schemas
class TestBase(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float

    class Config:
        from_attributes = True

class CentreResponse(BaseModel):
    id: int
    name: str
    location: str

    class Config:
        from_attributes = True

class CentreDetailResponse(BaseModel):
    id: int
    name: str
    location: str
    available_tests: List[TestBase] = []

    class Config:
        from_attributes = True

# Booking Schemas
class BookingCreate(BaseModel):
    centre_id: int
    test_id: int
    appointment_time: datetime

class BookingResponse(BaseModel):
    id: int
    user_id: int
    centre_id: int
    test_id: int
    appointment_time: datetime
    amount: float
    status: BookingStatus
    created_at: datetime

    class Config:
        from_attributes = True

# Payment Schemas
class PaymentSimulateRequest(BaseModel):
    booking_id: int
    outcome: str  # "SUCCESS" or "FAILED"

class PaymentWebhookRequest(BaseModel):
    event_id: str
    booking_id: int
    status: str   # "SUCCESS" or "FAILED"