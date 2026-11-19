from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_centre_admin
from app.database import get_db
from app.models.user import User
from app.schemas import PaymentWebhookRequest, PaymentWebhookResponse
from app.services import payment_service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/bookings/{booking_id}/confirm", response_model=PaymentWebhookResponse)
def confirm_booking_payment(
    booking_id: int,
    current_admin: User = Depends(require_centre_admin),
    db: Session = Depends(get_db),
) -> PaymentWebhookResponse:
    """Confirm pay-at-centre payment for a PENDING booking at the admin's diagnostic centre."""
    return payment_service.confirm_booking_payment_at_centre(
        db=db,
        current_admin=current_admin,
        booking_id=booking_id,
    )


@router.post("/webhook", response_model=PaymentWebhookResponse)
def payment_webhook(
    payload: PaymentWebhookRequest,
    db: Session = Depends(get_db),
) -> PaymentWebhookResponse:
    """Process an idempotent external payment gateway webhook."""
    return payment_service.process_payment_webhook(db, payload)
