from sqlalchemy.orm import Session

from app.models.payment import Payment, WebhookEvent


def get_payment_by_booking_id(db: Session, booking_id: int) -> Payment | None:
    return db.query(Payment).filter(Payment.booking_id == booking_id).first()


def create_payment(db: Session, payment: Payment) -> Payment:
    db.add(payment)
    db.flush()
    return payment


def get_webhook_event_by_event_id(db: Session, event_id: str) -> WebhookEvent | None:
    return db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()


def create_webhook_event(db: Session, webhook_event: WebhookEvent) -> WebhookEvent:
    db.add(webhook_event)
    db.flush()
    return webhook_event
