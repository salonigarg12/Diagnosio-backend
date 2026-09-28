from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.post("/", status_code=status.HTTP_200_OK)
def simulate_payment(
    payload: schemas.PaymentSimulateRequest,
    db: Session = Depends(get_db)
):
    # 1. Fetch the booking
    booking = db.query(models.Booking).filter(models.Booking.id == payload.booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {payload.booking_id} not found"
        )

    # 2. Check if the booking can be paid for
    if booking.status in [models.BookingStatus.CONFIRMED, models.BookingStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot process payment. Current booking status is {booking.status.value}"
        )

    # 3. Transition state based on simulated outcome
    if payload.outcome.upper() == "SUCCESS":
        booking.status = models.BookingStatus.CONFIRMED
    elif payload.outcome.upper() == "FAILED":
        booking.status = models.BookingStatus.FAILED
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outcome must be either 'SUCCESS' or 'FAILED'"
        )

    db.commit()
    db.refresh(booking)

    return {
        "message": f"Payment simulated with outcome: {payload.outcome.upper()}",
        "booking_id": booking.id,
        "booking_status": booking.status.value
    }

@router.post("/webhook/", status_code=status.HTTP_200_OK)
def payment_webhook(
    payload: schemas.PaymentWebhookRequest,
    db: Session = Depends(get_db)
):
    # --- IDEMPOTENCY CHECK ---
    # Check if this exact webhook event has already been recorded
    existing_event = db.query(models.WebhookEvent).filter(
        models.WebhookEvent.event_id == payload.event_id
    ).first()

    if existing_event:
        return {
            "status": "success",
            "message": "Event already processed (idempotent response)",
            "event_id": payload.event_id
        }

    # Verify booking exists before recording
    booking = db.query(models.Booking).filter(models.Booking.id == payload.booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {payload.booking_id} not found"
        )

    # Record the new webhook event to guarantee future requests are detected as duplicates
    webhook_record = models.WebhookEvent(
        event_id=payload.event_id,
        booking_id=payload.booking_id,
        status=payload.status.upper()
    )
    db.add(webhook_record)

    # Apply the status change to the booking
    if payload.status.upper() == "SUCCESS":
        booking.status = models.BookingStatus.CONFIRMED
    elif payload.status.upper() == "FAILED":
        booking.status = models.BookingStatus.FAILED

    db.commit()

    return {
        "status": "success",
        "message": "Webhook processed successfully",
        "event_id": payload.event_id,
        "booking_status": booking.status.value
    }