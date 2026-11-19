from decimal import Decimal
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.enums import BookingStatus, PaymentStatus
from app.models.booking import Booking, BookingItem
from app.models.payment import Payment
from app.models.user import User
from app.repositories import booking_repo, centre_repo, payment_repo
from app.schemas import BookingCreateRequest, BookingItemResponse, BookingResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


def serialize_booking(booking: Booking) -> BookingResponse:
    payment_status = (
        booking.payment.status if booking.payment is not None else PaymentStatus.PENDING
    )
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        patient_name=booking.user.full_name,
        patient_email=booking.user.email,
        centre_id=booking.centre_id,
        centre_name=booking.centre.name,
        centre_city=booking.centre.city,
        appointment_time=booking.appointment_time,
        total_amount=booking.total_amount,
        status=booking.status,
        payment_status=payment_status,
        created_at=booking.created_at,
        items=[
            BookingItemResponse(
                id=item.id,
                centre_test_id=item.centre_test_id,
                test_name_snapshot=item.test_name_snapshot,
                price_snapshot=item.price_snapshot,
            )
            for item in booking.items
        ],
    )


def create_booking(
    db: Session,
    current_user: User,
    payload: BookingCreateRequest,
) -> BookingResponse:
    """
    Concurrency-safe multi-test slot booking using PostgreSQL pessimistic locking.

    Transaction steps:
    1. Acquire SELECT ... FOR UPDATE row lock on the target Centre.
    2. Validate operating hours and prevent duplicate active bookings by the same user.
    3. Count active (PENDING / CONFIRMED) bookings for (centre_id, appointment_time).
    4. Capture price & test name snapshots into BookingItem records and insert Booking + Payment.
    5. Commit atomically (or roll back cleanly on any error).
    """
    try:
        # 1. Pessimistic row-level lock prevents TOCTOU race conditions on slot capacity.
        centre = booking_repo.lock_centre_for_update(db, payload.centre_id)
        if centre is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnostic centre not found.",
            )

        # 2. Validate that the fixed 1-hour slot is within centre operating hours.
        slot_hour = payload.appointment_time.hour
        if slot_hour < centre.opening_hour or slot_hour >= centre.closing_hour:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Selected slot is outside operating hours "
                    f"({centre.opening_hour:02d}:00 - {centre.closing_hour:02d}:00)."
                ),
            )

        # 3. Duplicate-booking safeguard for the same user on the same centre + slot.
        existing_user_booking = booking_repo.get_active_booking_for_user_slot(
            db=db,
            user_id=current_user.id,
            centre_id=centre.id,
            appointment_time=payload.appointment_time,
        )
        if existing_user_booking is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an active booking for this time slot.",
            )

        # 4. Verify remaining slot capacity under the centre row lock.
        active_bookings_count = booking_repo.count_active_bookings_for_slot(
            db=db,
            centre_id=centre.id,
            appointment_time=payload.appointment_time,
        )
        if active_bookings_count >= centre.max_capacity_per_slot:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Selected time slot is fully booked.",
            )

        # 5. Fetch selected CentreTest rows and capture price snapshots.
        centre_tests = centre_repo.get_centre_tests_by_ids(
            db=db,
            centre_id=centre.id,
            centre_test_ids=payload.centre_test_ids,
        )
        if len(centre_tests) != len(payload.centre_test_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more selected diagnostic tests are unavailable at this centre.",
            )

        total_amount = sum((ct.price for ct in centre_tests), Decimal("0.00"))
        booking = Booking(
            user_id=current_user.id,
            centre_id=centre.id,
            appointment_time=payload.appointment_time,
            total_amount=total_amount,
            status=BookingStatus.PENDING,
        )
        items = [
            BookingItem(
                centre_test_id=ct.id,
                test_name_snapshot=ct.test.name,
                price_snapshot=ct.price,
            )
            for ct in centre_tests
        ]

        booking_repo.create_booking_with_items(db, booking, items)
        payment_repo.create_payment(
            db,
            Payment(
                booking_id=booking.id,
                amount=total_amount,
                status=PaymentStatus.PENDING,
            ),
        )

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to create booking: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create booking.",
        )

    created = booking_repo.get_by_id(db, booking.id)
    return serialize_booking(created)


def list_my_bookings(db: Session, current_user: User) -> List[BookingResponse]:
    """Return all bookings belonging to the authenticated patient."""
    bookings = booking_repo.list_by_user(db, current_user.id)
    return [serialize_booking(b) for b in bookings]


def cancel_booking(
    db: Session,
    current_user: User,
    booking_id: int,
) -> BookingResponse:
    """
    Cancel a PENDING booking and immediately release its slot capacity.
    CONFIRMED bookings are locked and cannot be cancelled.
    """
    try:
        booking = booking_repo.get_by_id_for_update(db, booking_id)
        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        if booking.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to cancel this booking.",
            )

        if booking.status == BookingStatus.CONFIRMED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confirmed bookings cannot be cancelled.",
            )

        if booking.status == BookingStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking is already cancelled.",
            )

        if booking.status != BookingStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending bookings can be cancelled.",
            )

        booking.status = BookingStatus.CANCELLED
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to cancel booking: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to cancel booking.",
        )

    updated = booking_repo.get_by_id(db, booking.id)
    return serialize_booking(updated)
