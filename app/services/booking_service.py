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
            raise HTTPException(status_code=400, detail="At least one test must be selected.")

        centre = self.centre_repo.get_by_id(payload.centre_id)
        if not centre:
            raise HTTPException(status_code=404, detail="Diagnostic centre not found.")

        # Check pricing and availability for all requested tests
        offered_tests = self.centre_repo.get_centre_tests(payload.centre_id, payload.test_ids)
        if len(offered_tests) != len(payload.test_ids):
            offered_ids = {t.test_id for t in offered_tests}
            missing = set(payload.test_ids) - offered_ids
            raise HTTPException(
                status_code=400, 
                detail=f"Tests with IDs {list(missing)} are not offered at this centre."
            )

        total_amount = sum(t.price for t in offered_tests)
        pricing_breakdown = [{"test_id": t.test_id, "price": t.price} for t in offered_tests]

        return self.booking_repo.create_booking(
            user_id=user_id,
            centre_id=payload.centre_id,
            appointment_time=payload.appointment_time,
            total_amount=total_amount,
            test_pricing=pricing_breakdown
        )

    def process_webhook_event(self, payload: WebhookPayload):
        # 1. Idempotency Check
        existing_event = self.booking_repo.get_webhook_event(payload.event_id)
        if existing_event:
            return {
                "message": "Event already processed (idempotent response)", 
                "event_id": payload.event_id,
                "status": "DUPLICATE_IGNORED"
            }

        # 2. Verify Booking
        booking = self.booking_repo.get_by_id(payload.booking_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found for this webhook event")

        # 3. Transition State & Ledger
        new_status = BookingStatus.CONFIRMED.value if payload.status == "SUCCESS" else BookingStatus.FAILED.value
        self.booking_repo.update_status(booking, new_status)
        self.booking_repo.create_payment(
            booking_id=booking.id,
            amount=booking.total_amount,
            status=PaymentStatus.SUCCESS.value if payload.status == "SUCCESS" else PaymentStatus.FAILED.value,
            txn_id=f"txn_{payload.event_id}"
        )
        self.booking_repo.record_webhook_event(payload.event_id, payload.booking_id, payload.status)

        return {
            "message": "Webhook processed successfully",
            "booking_id": booking.id,
            "booking_status": booking.status
        }