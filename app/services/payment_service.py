from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.booking_repo import BookingRepository
from app.constants.enums import BookingStatus, PaymentStatus
from app.schemas import WebhookPayload
from app.utils.logger import logger

class PaymentService:
    def __init__(self, db: Session):
        self.booking_repo = BookingRepository(db)

    def process_webhook_event(self, payload: WebhookPayload) -> dict:
        logger.info(f"Webhook received: event_id={payload.event_id}, booking_id={payload.booking_id}")

        # 1. Idempotency Check
        existing_event = self.booking_repo.get_webhook_event_by_id(payload.event_id)
        if existing_event:
            logger.warning(
                f"Duplicate webhook detected: event_id={payload.event_id} has already been processed. "
                "Skipping mutation."
            )
            return {
                "message": "Event already processed (idempotent response)",
                "event_id": payload.event_id,
                "status": "DUPLICATE_IGNORED",
            }

        # 2. Check booking existence
        booking = self.booking_repo.get_by_id(payload.booking_id)
        if not booking:
            logger.error(f"Webhook processing error: Target booking_id={payload.booking_id} not found")
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

        logger.info(
            f"Processing payment outcome for booking_id={booking.id}: "
            f"payload_status={payload.status} -> target_booking_status={next_booking_status}"
        )

        try:
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
            logger.info(
                f"Webhook processed successfully: event_id={payload.event_id}, "
                f"booking_id={booking.id}, status={next_booking_status}"
            )
        except Exception as exc:
            logger.error(
                f"Database error while recording webhook transaction for event_id={payload.event_id}: {exc}",
                exc_info=True
            )
            raise exc

        return {
            "message": "Webhook processed successfully",
            "booking_id": booking.id,
            "booking_status": next_booking_status,
        }