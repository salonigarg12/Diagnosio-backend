from datetime import date, datetime, time
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.constants.enums import BookingStatus
from app.models.booking import Booking, BookingItem
from app.models.centre import Centre

ACTIVE_BOOKING_STATUSES = [BookingStatus.PENDING, BookingStatus.CONFIRMED]


def lock_centre_for_update(db: Session, centre_id: int) -> Centre | None:
    """Acquire a PostgreSQL row-level lock (SELECT ... FOR UPDATE) on the target Centre."""
    return (
        db.query(Centre)
        .filter(Centre.id == centre_id)
        .with_for_update()
        .first()
    )


def count_active_bookings_for_slot(
    db: Session,
    centre_id: int,
    appointment_time: datetime,
) -> int:
    """Count PENDING and CONFIRMED bookings occupying a given centre + hourly slot."""
    count = (
        db.query(func.count(Booking.id))
        .filter(
            Booking.centre_id == centre_id,
            Booking.appointment_time == appointment_time,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        )
        .scalar()
    )
    return int(count or 0)


def get_active_booking_for_user_slot(
    db: Session,
    user_id: int,
    centre_id: int,
    appointment_time: datetime,
) -> Booking | None:
    """Check whether the same user already holds an active booking for this exact slot."""
    return (
        db.query(Booking)
        .filter(
            Booking.user_id == user_id,
            Booking.centre_id == centre_id,
            Booking.appointment_time == appointment_time,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        )
        .first()
    )


def get_slot_booking_counts_for_date(
    db: Session,
    centre_id: int,
    target_date: date,
) -> Dict[int, int]:
    """Return a map of {hour: active_booking_count} for a centre on a specific calendar date."""
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    rows = (
        db.query(Booking.appointment_time)
        .filter(
            Booking.centre_id == centre_id,
            Booking.appointment_time >= day_start,
            Booking.appointment_time <= day_end,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        )
        .all()
    )

    counts: Dict[int, int] = {}
    for (appt_dt,) in rows:
        counts[appt_dt.hour] = counts.get(appt_dt.hour, 0) + 1
    return counts


def create_booking_with_items(
    db: Session,
    booking: Booking,
    items: List[BookingItem],
) -> Booking:
    db.add(booking)
    db.flush()
    for item in items:
        item.booking_id = booking.id
        db.add(item)
    db.flush()
    return booking


def get_by_id(db: Session, booking_id: int) -> Booking | None:
    return (
        db.query(Booking)
        .options(
            joinedload(Booking.user),
            joinedload(Booking.centre),
            joinedload(Booking.items),
            joinedload(Booking.payment),
        )
        .filter(Booking.id == booking_id)
        .first()
    )


def get_by_id_for_update(db: Session, booking_id: int) -> Booking | None:
    """Lock a specific Booking row before status transitions (payment or cancellation)."""
    return (
        db.query(Booking)
        .filter(Booking.id == booking_id)
        .with_for_update()
        .first()
    )


def list_by_user(db: Session, user_id: int) -> List[Booking]:
    return (
        db.query(Booking)
        .options(
            joinedload(Booking.user),
            joinedload(Booking.centre),
            joinedload(Booking.items),
            joinedload(Booking.payment),
        )
        .filter(Booking.user_id == user_id)
        .order_by(Booking.appointment_time.desc(), Booking.id.desc())
        .all()
    )


def list_by_centre(
    db: Session,
    centre_id: int,
    booking_date: Optional[date] = None,
    status: Optional[BookingStatus] = None,
) -> List[Booking]:
    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.user),
            joinedload(Booking.centre),
            joinedload(Booking.items),
            joinedload(Booking.payment),
        )
        .filter(Booking.centre_id == centre_id)
    )
    if booking_date is not None:
        day_start = datetime.combine(booking_date, time.min)
        day_end = datetime.combine(booking_date, time.max)
        query = query.filter(
            Booking.appointment_time >= day_start,
            Booking.appointment_time <= day_end,
        )
    if status is not None:
        query = query.filter(Booking.status == status)

    return query.order_by(Booking.appointment_time.desc(), Booking.id.desc()).all()
