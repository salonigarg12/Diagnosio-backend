from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import schemas, models
from app.auth import get_current_user
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("/", response_model=schemas.BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_data: schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return BookingService(db).create_multi_test_booking(current_user.id, booking_data)

@router.get("/", response_model=List[schemas.BookingResponse])
def get_user_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return BookingService(db).get_user_bookings(current_user.id)

@router.get("/{booking_id}", response_model=schemas.BookingResponse)
def get_booking_detail(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return BookingService(db).get_booking_detail(booking_id, current_user.id)

@router.patch("/{booking_id}/status", response_model=schemas.BookingResponse)
def update_booking_status(
    booking_id: int,
    status_update: schemas.BookingStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return BookingService(db).update_diagnostic_status(booking_id, status_update.status)