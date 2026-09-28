from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import schemas, models
from app.auth import get_current_user
from app.services.booking_service import BookingService
from app.repositories.booking_repo import BookingRepository
from app.constants.enums import BookingStatus

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("/", response_model=schemas.BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_data: schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    service = BookingService(db)
    return service.create_multi_test_booking(current_user.id, booking_data)

@router.get("/", response_model=List[schemas.BookingResponse])
def get_user_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    repo = BookingRepository(db)
    return repo.get_by_user(current_user.id)

@router.get("/{booking_id}", response_model=schemas.BookingResponse)
def get_booking_detail(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    repo = BookingRepository(db)
    booking = repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this booking.")
    return booking

@router.patch("/{booking_id}/status", response_model=schemas.BookingResponse)
def update_status(
    booking_id: int,
    status_update: schemas.BookingStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Enforces state transition machine: PENDING -> CONFIRMED -> SAMPLE_COLLECTED -> REPORT_GENERATED -> COMPLETED
    repo = BookingRepository(db)
    booking = repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    return repo.update_status(booking, status_update.status.value)