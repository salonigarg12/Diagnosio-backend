from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import require_patient
from app.database import get_db
from app.models.user import User
from app.schemas import BookingCreateRequest, BookingResponse
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post(
    "/",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
    payload: BookingCreateRequest,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Create a concurrency-safe multi-test booking for a fixed 1-hour slot."""
    return booking_service.create_booking(db, current_user, payload)


@router.get("/my", response_model=List[BookingResponse])
def list_my_bookings(
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
) -> List[BookingResponse]:
    """List all personal bookings for the authenticated patient."""
    return booking_service.list_my_bookings(db, current_user)


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: int,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Cancel a PENDING booking and release slot capacity immediately."""
    return booking_service.cancel_booking(db, current_user, booking_id)
