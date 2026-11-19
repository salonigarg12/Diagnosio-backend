import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.enums import BookingStatus, PaymentStatus
from app.models.payment import Payment, WebhookEvent
from app.models.user import User
from app.repositories import booking_repo, payment_repo
from app.schemas import PaymentWebhookRequest, PaymentWebhookResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


def process_payment_webhook(
    db: Session,
    payload: PaymentWebhookRequest,
) -> PaymentWebhookResponse:
    """
    Idempotent payment webhook processor.

    If `event_id` has already been recorded in `webhook_events`, returns the current
    booking and payment state safely without duplicating state transitions.
    """
    existing_event = payment_repo.get_webhook_event_by_event_id(db, payload.event_id)
    if existing_event is not None:
        booking = booking_repo.get_by_id(db, existing_event.booking_id)
        payment_status = (
            booking.payment.status
            if booking and booking.payment is not None
            else PaymentStatus.PENDING
        )
        return PaymentWebhookResponse(
            event_id=existing_event.event_id,
            booking_id=existing_event.booking_id,
            booking_status=booking.status if booking else BookingStatus.PENDING,
            payment_status=payment_status,
            idempotent_replay=True,
            message="Webhook event already processed (idempotent replay).",
        )

    try:
        booking = booking_repo.get_by_id_for_update(db, payload.booking_id)
        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        if booking.status == BookingStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot confirm payment for a cancelled booking.",
            )

        payment = payment_repo.get_payment_by_booking_id(db, booking.id)
        if payment is None:
            payment = Payment(
                booking_id=booking.id,
                amount=booking.total_amount,
                status=payload.status,
                transaction_ref=payload.transaction_ref or f"TXN-{payload.event_id}",
            )
            payment_repo.create_payment(db, payment)
        else:
            payment.status = payload.status
            if payload.transaction_ref:
                payment.transaction_ref = payload.transaction_ref
            elif not payment.transaction_ref:
                payment.transaction_ref = f"TXN-{payload.event_id}"

        if payload.status == PaymentStatus.SUCCESS:
            booking.status = BookingStatus.CONFIRMED

        event = WebhookEvent(
            event_id=payload.event_id,
            event_type=f"payment.{payload.status.value.lower()}",
            booking_id=booking.id,
            payload=json.dumps(payload.model_dump(mode="json")),
        )
        payment_repo.create_webhook_event(db, event)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to process payment webhook: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process payment webhook.",
        )

    return PaymentWebhookResponse(
        event_id=payload.event_id,
        booking_id=booking.id,
        booking_status=booking.status,
        payment_status=payment.status,
        idempotent_replay=False,
        message="Payment webhook processed successfully.",
    )


def confirm_booking_payment_at_centre(
    db: Session,
    current_admin: User,
    booking_id: int,
) -> PaymentWebhookResponse:
    """
    Allow a CENTRE_ADMIN to confirm pay-at-centre payment for a PENDING booking
    belonging to their own diagnostic centre via the idempotent webhook flow.
    """
    booking = booking_repo.get_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )

    if booking.centre.owner_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to confirm payment for another centre's booking.",
        )

    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot confirm payment for a cancelled booking.",
        )

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending bookings can be confirmed.",
        )

    webhook_payload = PaymentWebhookRequest(
        event_id=f"counter-confirm-{booking_id}",
        booking_id=booking_id,
        status=PaymentStatus.SUCCESS,
        transaction_ref=f"COUNTER-{booking_id}",
    )
    return process_payment_webhook(db, webhook_payload)
