from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("/", response_model=schemas.BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_data: schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Verify centre offers this test and get the exact price
    centre_test = db.query(models.CentreTest).filter(
        models.CentreTest.centre_id == booking_data.centre_id,
        models.CentreTest.test_id == booking_data.test_id
    ).first()

    if not centre_test:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected diagnostic centre does not offer this test."
        )

    # 2. Create the booking with status PENDING
    new_booking = models.Booking(
        user_id=current_user.id,
        centre_id=booking_data.centre_id,
        test_id=booking_data.test_id,
        appointment_time=booking_data.appointment_time,
        amount=centre_test.price,
        status=models.BookingStatus.PENDING
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking

@router.get("/", response_model=List[schemas.BookingResponse])
def get_user_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Only return bookings that belong to this logged-in user
    bookings = db.query(models.Booking).filter(models.Booking.user_id == current_user.id).all()
    return bookings

@router.get("/{booking_id}", response_model=schemas.BookingResponse)
def get_booking_detail(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    
    # Edge case: Booking does not exist
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {booking_id} not found"
        )
    
    # Edge case: Unauthorized user trying to view someone else's booking
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this booking"
        )

    return booking