from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.booking_repo import BookingRepository
from app.constants.enums import BookingStatus, PaymentStatus
from app.schemas import WebhookPayload

class PaymentService:
    def __init__(self, db: Session):
        self.booking_repo = BookingRepository(db)

    def process_webhook_event(self, payload: WebhookPayload) -> dict:
        # 1. Idempotency Check
        existing_event = self.booking_repo.get_webhook_event_by_id(payload.event_id)
        if existing_event:
            return {
                "message": "Event already processed (idempotent response)",
                "event_id": payload.event_id,
                "status": "DUPLICATE_IGNORED",
            }

        # 2. Check booking existence
        booking = self.booking_repo.get_by_id(payload.booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found for this webhook event",
            )

        # 3. Determine status transitions
        is_success = payload.status.upper() == "SUCCESS"
        next_booking_status = (
            BookingStatus.CONFIRMED.value if is_success else BookingStatus.FAILED.value
        )
        payment_status = (
            PaymentStatus.SUCCESS.value if is_success else PaymentStatus.FAILED.value
        )

        # 4. State updates and ledger recording
        self.booking_repo.update_booking_status(booking.id, next_booking_status)
        self.booking_repo.create_payment_record(
            booking_id=booking.id,
            amount=booking.total_amount,
            status=payment_status,
            txn_id=f"txn_{payload.event_id}",
        )
        self.booking_repo.record_webhook_event(
            payload.event_id, payload.booking_id, payload.status
        )

        return {
            "message": "Webhook processed successfully",
            "booking_id": booking.id,
            "booking_status": next_booking_status,
        }