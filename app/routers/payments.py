from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.services.booking_service import BookingService

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.post("/webhook/")
def payment_webhook(payload: schemas.WebhookPayload, db: Session = Depends(get_db)):
    service = BookingService(db)
    return service.process_webhook_event(payload)