from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth import require_centre_admin
from app.constants.enums import BookingStatus
from app.database import get_db
from app.models.user import User
from app.schemas import (
    CentreAdminDashboardResponse,
    CentreCreateRequest,
    CentreResponse,
    CentreTestResponse,
    CentreTestUpsertRequest,
    SlotAvailabilityResponse,
)
from app.services import centre_service

router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])


@router.get("/", response_model=List[CentreResponse])
def list_centres(
    city: Optional[str] = Query(default=None, description="Filter centres by city"),
    search: Optional[str] = Query(default=None, description="Search centres by name or address"),
    db: Session = Depends(get_db),
) -> List[CentreResponse]:
    """Browse onboarded diagnostic centres and their available tests."""
    return centre_service.list_centres(db, city=city, search=search)


@router.post(
    "/",
    response_model=CentreResponse,
    status_code=status.HTTP_201_CREATED,
)
def onboard_centre(
    payload: CentreCreateRequest,
    current_user: User = Depends(require_centre_admin),
    db: Session = Depends(get_db),
) -> CentreResponse:
    """Self-service onboarding for a CENTRE_ADMIN (max one centre per admin)."""
    return centre_service.onboard_centre(db, current_user, payload)


@router.get("/my-centre", response_model=CentreAdminDashboardResponse)
def get_my_centre(
    booking_date: Optional[date] = Query(default=None, description="Filter appointments by date"),
    booking_status: Optional[BookingStatus] = Query(
        default=None,
        alias="status",
        description="Filter appointments by booking status",
    ),
    current_user: User = Depends(require_centre_admin),
    db: Session = Depends(get_db),
) -> CentreAdminDashboardResponse:
    """Return the authenticated centre admin's centre profile, tests, stats, and bookings."""
    return centre_service.get_my_centre_dashboard(
        db=db,
        current_user=current_user,
        booking_date=booking_date,
        booking_status=booking_status,
    )


@router.post(
    "/{centre_id}/tests",
    response_model=CentreTestResponse,
    status_code=status.HTTP_201_CREATED,
)
def upsert_centre_test(
    centre_id: int,
    payload: CentreTestUpsertRequest,
    current_user: User = Depends(require_centre_admin),
    db: Session = Depends(get_db),
) -> CentreTestResponse:
    """Add or update a diagnostic test and price for an admin's owned centre."""
    return centre_service.upsert_centre_test(db, current_user, centre_id, payload)


@router.get("/{centre_id}/slots", response_model=List[SlotAvailabilityResponse])
def get_centre_slots(
    centre_id: int,
    booking_date: date = Query(..., description="Target calendar date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[SlotAvailabilityResponse]:
    """Return fixed 1-hour slots and live remaining capacity for a centre on a given date."""
    return centre_service.get_centre_slots(db, centre_id, booking_date)
