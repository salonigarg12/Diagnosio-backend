from datetime import date, datetime, time
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.enums import BookingStatus
from app.models.centre import Centre, CentreTest
from app.models.user import User
from app.repositories import booking_repo, centre_repo
from app.schemas import (
    CentreAdminDashboardResponse,
    CentreCreateRequest,
    CentreResponse,
    CentreStatsResponse,
    CentreTestResponse,
    CentreTestUpsertRequest,
    SlotAvailabilityResponse,
)
from app.services.booking_service import serialize_booking
from app.utils.cache import catalogue_cache
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _serialize_centre_test(centre_test: CentreTest) -> CentreTestResponse:
    return CentreTestResponse(
        centre_test_id=centre_test.id,
        test_id=centre_test.test_id,
        test_name=centre_test.test.name,
        description=centre_test.test.description,
        price=centre_test.price,
        is_available=centre_test.is_available,
    )


def serialize_centre(centre: Centre, include_unavailable: bool = False) -> CentreResponse:
    tests = [
        _serialize_centre_test(ct)
        for ct in sorted(centre.centre_tests, key=lambda x: x.id)
        if include_unavailable or ct.is_available
    ]
    return CentreResponse(
        id=centre.id,
        owner_id=centre.owner_id,
        name=centre.name,
        city=centre.city,
        address=centre.address,
        opening_hour=centre.opening_hour,
        closing_hour=centre.closing_hour,
        max_capacity_per_slot=centre.max_capacity_per_slot,
        created_at=centre.created_at,
        tests=tests,
    )


def list_centres(
    db: Session,
    city: Optional[str] = None,
    search: Optional[str] = None,
) -> List[CentreResponse]:
    """List onboarded diagnostic centres with TTL caching."""
    cache_key = f"centres:{(city or '').strip().lower()}:{(search or '').strip().lower()}"
    cached = catalogue_cache.get(cache_key)
    if cached is not None:
        return [CentreResponse.model_validate(item) for item in cached]

    centres = centre_repo.list_centres(db, city=city, search=search)
    responses = [serialize_centre(c, include_unavailable=False) for c in centres]
    catalogue_cache.set(
        cache_key,
        [item.model_dump(mode="json") for item in responses],
    )
    return responses


def get_centre_slots(
    db: Session,
    centre_id: int,
    target_date: date,
) -> List[SlotAvailabilityResponse]:
    """Generate fixed 1-hour slots from operating hours with live remaining capacity."""
    centre = centre_repo.get_by_id(db, centre_id)
    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostic centre not found.",
        )

    counts_by_hour = booking_repo.get_slot_booking_counts_for_date(
        db=db,
        centre_id=centre.id,
        target_date=target_date,
    )

    slots: List[SlotAvailabilityResponse] = []
    for hour in range(centre.opening_hour, centre.closing_hour):
        slot_dt = datetime.combine(target_date, time(hour=hour, minute=0))
        booked_count = counts_by_hour.get(hour, 0)
        available_spots = max(0, centre.max_capacity_per_slot - booked_count)
        slots.append(
            SlotAvailabilityResponse(
                slot_time=slot_dt,
                label=f"{hour:02d}:00 - {hour + 1:02d}:00",
                booked_count=booked_count,
                max_capacity=centre.max_capacity_per_slot,
                available_spots=available_spots,
                is_available=available_spots > 0,
            )
        )
    return slots


def onboard_centre(
    db: Session,
    current_user: User,
    payload: CentreCreateRequest,
) -> CentreResponse:
    """Onboard a diagnostic centre for a CENTRE_ADMIN (strictly one centre per admin)."""
    existing = centre_repo.get_by_owner_id(db, current_user.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already onboarded a diagnostic centre.",
        )

    try:
        centre = Centre(
            owner_id=current_user.id,
            name=payload.name.strip(),
            city=payload.city.strip(),
            address=payload.address.strip(),
            opening_hour=payload.opening_hour,
            closing_hour=payload.closing_hour,
            max_capacity_per_slot=payload.max_capacity_per_slot,
        )
        centre_repo.create_centre(db, centre)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to onboard centre: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register diagnostic centre.",
        )

    catalogue_cache.clear()
    loaded = centre_repo.get_by_id(db, centre.id)
    return serialize_centre(loaded, include_unavailable=True)


def upsert_centre_test(
    db: Session,
    current_user: User,
    centre_id: int,
    payload: CentreTestUpsertRequest,
) -> CentreTestResponse:
    """Add or update a diagnostic test and its price for an admin's owned centre."""
    centre = centre_repo.get_by_id(db, centre_id)
    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostic centre not found.",
        )

    if centre.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to manage tests for another centre.",
        )

    try:
        test = centre_repo.get_or_create_test(
            db=db,
            name=payload.test_name,
            description=payload.description,
        )
        centre_test = centre_repo.upsert_centre_test(
            db=db,
            centre_id=centre.id,
            test_id=test.id,
            price=payload.price,
            is_available=payload.is_available,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to upsert diagnostic test: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save diagnostic test.",
        )

    # Invalidate catalogue cache so patients immediately see updated tests/prices.
    catalogue_cache.clear()
    return _serialize_centre_test(centre_test)


def get_my_centre_dashboard(
    db: Session,
    current_user: User,
    booking_date: Optional[date] = None,
    booking_status: Optional[BookingStatus] = None,
) -> CentreAdminDashboardResponse:
    """Return the admin's onboarded centre profile, offered tests, stats, and bookings."""
    centre = centre_repo.get_by_owner_id(db, current_user.id)
    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No diagnostic centre onboarded yet for this admin.",
        )

    all_bookings = booking_repo.list_by_centre(db, centre.id)
    filtered_bookings = booking_repo.list_by_centre(
        db=db,
        centre_id=centre.id,
        booking_date=booking_date,
        status=booking_status,
    )

    stats = CentreStatsResponse(
        total_bookings=len(all_bookings),
        pending_bookings=sum(1 for b in all_bookings if b.status == BookingStatus.PENDING),
        confirmed_bookings=sum(1 for b in all_bookings if b.status == BookingStatus.CONFIRMED),
        cancelled_bookings=sum(1 for b in all_bookings if b.status == BookingStatus.CANCELLED),
        offered_tests_count=len(centre.centre_tests),
    )

    return CentreAdminDashboardResponse(
        centre=serialize_centre(centre, include_unavailable=True),
        stats=stats,
        bookings=[serialize_booking(b) for b in filtered_bookings],
    )
