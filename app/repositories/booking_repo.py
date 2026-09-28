from sqlalchemy.orm import Session
from app.models import Booking, BookingItem, Payment, WebhookEvent
from app.constants.enums import BookingStatus

class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_booking(self, user_id: int, centre_id: int, appointment_time, total_amount: float, test_pricing: list[dict]):
        booking = Booking(
            user_id=user_id,
            centre_id=centre_id,
            appointment_time=appointment_time,
            total_amount=total_amount,
            status=BookingStatus.PENDING.value
        )
        self.db.add(booking)
        self.db.flush()

        for item in test_pricing:
            b_item = BookingItem(
                booking_id=booking.id,
                test_id=item["test_id"],
                price_at_booking=item["price"]
            )
            self.db.add(b_item)

        self.db.commit()
        self.db.refresh(booking)
        return booking

    def get_by_id(self, booking_id: int):
        return self.db.query(Booking).filter(Booking.id == booking_id).first()

    def get_by_user(self, user_id: int):
        return self.db.query(Booking).filter(Booking.user_id == user_id).all()

    def update_status(self, booking: Booking, new_status: str):
        booking.status = new_status
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def create_payment(self, booking_id: int, amount: float, status: str, txn_id: str):
        payment = Payment(booking_id=booking_id, amount=amount, status=status, transaction_id=txn_id)
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def get_webhook_event(self, event_id: str):
        return self.db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()

    def record_webhook_event(self, event_id: str, booking_id: int, status: str):
        event = WebhookEvent(event_id=event_id, booking_id=booking_id, status=status)
        self.db.add(event)
        self.db.commit()
        return event