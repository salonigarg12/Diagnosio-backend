from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.booking_repo import BookingRepository
from app.repositories.centre_repo import CentreRepository
from app.constants.enums import BookingStatus
from app.schemas import BookingCreate
from app.utils.logger import logger

class BookingService:
    def __init__(self, db: Session):
        self.booking_repo = BookingRepository(db)
        self.centre_repo = CentreRepository(db)

    def create_multi_test_booking(self, user_id: int, payload: BookingCreate):
        logger.info(
            f"Initiating booking creation for user_id={user_id} at centre_id={payload.centre_id} "
            f"with {len(payload.test_ids)} test(s)"
        )

        if not payload.test_ids:
            logger.warning(f"Booking rejected: Empty test list supplied by user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one test must be selected."
            )

        centre = self.centre_repo.get_by_id(payload.centre_id)
        if not centre:
            logger.warning(f"Booking rejected: centre_id={payload.centre_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnostic centre not found."
            )

        offered_tests = self.centre_repo.get_centre_tests_by_ids(
            payload.centre_id, payload.test_ids
        )
        if len(offered_tests) != len(payload.test_ids):
            offered_ids = {t.test_id for t in offered_tests}
            missing_ids = set(payload.test_ids) - offered_ids
            logger.warning(
                f"Booking rejected: centre_id={payload.centre_id} does not offer tests={list(missing_ids)}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tests with IDs {list(missing_ids)} are not offered at this centre."
            )

        total_amount = sum(t.price for t in offered_tests)
        pricing_breakdown = [
            {"test_id": t.test_id, "price": t.price} for t in offered_tests
        ]

        logger.info(
            f"Validated tests for user_id={user_id}. Aggregated total_amount={total_amount:.2f}. "
            "Persisting booking records..."
        )

        try:
            booking = self.booking_repo.create_booking_with_items(
                user_id=user_id,
                centre_id=payload.centre_id,
                appointment_time=payload.appointment_time,
                total_amount=total_amount,
                test_items=pricing_breakdown,
            )
            logger.info(
                f"Booking created successfully: booking_id={booking.id}, "
                f"status={booking.status}, amount={booking.total_amount:.2f}"
            )
            return booking
        except Exception as exc:
            logger.error(
                f"Failed to persist booking for user_id={user_id} at centre_id={payload.centre_id}: {exc}",
                exc_info=True
            )
            raise exc

    def get_user_bookings(self, user_id: int):
        logger.debug(f"Fetching all bookings for user_id={user_id}")
        return self.booking_repo.get_by_user_id(user_id)

    def get_booking_detail(self, booking_id: int, requesting_user_id: int):
        logger.debug(f"Retrieving booking_id={booking_id} for user_id={requesting_user_id}")
        booking = self.booking_repo.get_by_id(booking_id)
        if not booking:
            logger.warning(f"Booking lookup failed: booking_id={booking_id} does not exist")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found."
            )
        if booking.user_id != requesting_user_id:
            logger.warning(
                f"Access denied: user_id={requesting_user_id} attempted unauthorized access to booking_id={booking_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not own this booking."
            )
        return booking

    def update_diagnostic_status(self, booking_id: int, new_status: BookingStatus):
        logger.info(f"Attempting lifecycle state update for booking_id={booking_id} to status={new_status.value}")
        booking = self.booking_repo.get_by_id(booking_id)
        if not booking:
            logger.warning(f"Status update failed: booking_id={booking_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found."
            )

        previous_status = booking.status
        updated_booking = self.booking_repo.update_booking_status(booking_id, new_status.value)
        logger.info(
            f"Diagnostic lifecycle updated: booking_id={booking_id} transitioned from {previous_status} -> {new_status.value}"
        )
        return updated_booking