from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.booking_repo import BookingRepository
from app.repositories.centre_repo import CentreRepository
from app.constants.enums import BookingStatus, PaymentStatus
from app.schemas import BookingCreate, WebhookPayload

class BookingService:
    def __init__(self, db: Session):
        self.booking_repo = BookingRepository(db)
        self.centre_repo = CentreRepository(db)

    def create_multi_test_booking(self, user_id: int, payload: BookingCreate):
        if not payload.test_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one test must be selected."
            )

        # 1. Delegate existence check to CentreRepo
        centre = self.centre_repo.get_by_id(payload.centre_id)
        if not centre:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnostic centre not found."
            )

        # 2. Delegate availability check to CentreRepo
        offered_tests = self.centre_repo.get_centre_tests_by_ids(payload.centre_id, payload.test_ids)
        if len(offered_tests) != len(payload.test_ids):
            offered_ids = {t.test_id for t in offered_tests}
            missing_ids = set(payload.test_ids) - offered_ids
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tests with IDs {list(missing_ids)} are not offered at this centre."
            )

        # 3. Calculate Pricing Logic
        total_amount = sum(t.price for t in offered_tests)
        pricing_breakdown = [{"test_id": t.test_id, "price": t.price} for t in offered_tests]

        # 4. Delegate DB transaction to BookingRepo
        return self.booking_repo.create_booking_with_items(
            user_id=user_id,
            centre_id=payload.centre_id,
            appointment_time=payload.appointment_time,
            total_amount=total_amount,
            test_items=pricing_breakdown
        )

    def get_user_bookings(self, user_id: int):
        return self.booking_repo.get_by_user_id(user_id)

    def get_booking_detail(self, booking_id: int, requesting_user_id: int):
        booking = self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found."
            )
        # Authorization check
        if booking.user_id != requesting_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not own this booking."
            )
        return booking

    def update_diagnostic_status(self, booking_id: int, new_status: BookingStatus):
        booking = self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found."
            )
        return self.booking_repo.update_booking_status(booking_id, new_status.value)

    def process_webhook_event(self, payload: WebhookPayload):
        # 1. Check idempotency via BookingRepo
        existing_event = self.booking_repo.get_webhook_event_by_id(payload.event_id)
        if existing_event:
            return {
                "message": "Event already processed (idempotent response)",
                "event_id": payload.event_id,
                "status": "DUPLICATE_IGNORED"
            }

        # 2. Check booking via BookingRepo
        booking = self.booking_repo.get_by_id(payload.booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found for this webhook event"
            )

        # 3. Determine status transition
        is_success = (payload.status.upper() == "SUCCESS")
        next_booking_status = BookingStatus.CONFIRMED.value if is_success else BookingStatus.FAILED.value
        payment_status = PaymentStatus.SUCCESS.value if is_success else PaymentStatus.FAILED.value

        # 4. Delegate mutations to BookingRepo
        self.booking_repo.update_booking_status(booking.id, next_booking_status)
        self.booking_repo.create_payment_record(
            booking_id=booking.id,
            amount=booking.total_amount,
            status=payment_status,
            txn_id=f"txn_{payload.event_id}"
        )
        self.booking_repo.record_webhook_event(payload.event_id, payload.booking_id, payload.status)

        return {
            "message": "Webhook processed successfully",
            "booking_id": booking.id,
            "booking_status": next_booking_status
        }