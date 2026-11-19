from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.centre import Centre, CentreTest, Test


def get_by_id(db: Session, centre_id: int) -> Centre | None:
    return (
        db.query(Centre)
        .options(joinedload(Centre.centre_tests).joinedload(CentreTest.test))
        .filter(Centre.id == centre_id)
        .first()
    )


def get_by_owner_id(db: Session, owner_id: int) -> Centre | None:
    return (
        db.query(Centre)
        .options(joinedload(Centre.centre_tests).joinedload(CentreTest.test))
        .filter(Centre.owner_id == owner_id)
        .first()
    )


def list_centres(
    db: Session,
    city: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Centre]:
    query = db.query(Centre).options(
        joinedload(Centre.centre_tests).joinedload(CentreTest.test)
    )
    if city:
        query = query.filter(Centre.city.ilike(f"%{city.strip()}%"))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Centre.name.ilike(term) | Centre.address.ilike(term) | Centre.city.ilike(term)
        )
    return query.order_by(Centre.id.asc()).all()


def create_centre(db: Session, centre: Centre) -> Centre:
    db.add(centre)
    db.flush()
    return centre


def get_or_create_test(db: Session, name: str, description: str) -> Test:
    existing = (
        db.query(Test)
        .filter(func.lower(Test.name) == name.strip().lower())
        .first()
    )
    if existing:
        if description and not existing.description:
            existing.description = description
            db.flush()
        return existing

    new_test = Test(name=name.strip(), description=description.strip())
    db.add(new_test)
    db.flush()
    return new_test


def upsert_centre_test(
    db: Session,
    centre_id: int,
    test_id: int,
    price: Decimal,
    is_available: bool = True,
) -> CentreTest:
    existing = (
        db.query(CentreTest)
        .options(joinedload(CentreTest.test))
        .filter(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == test_id,
        )
        .first()
    )
    if existing:
        existing.price = price
        existing.is_available = is_available
        db.flush()
        return existing

    centre_test = CentreTest(
        centre_id=centre_id,
        test_id=test_id,
        price=price,
        is_available=is_available,
    )
    db.add(centre_test)
    db.flush()
    return (
        db.query(CentreTest)
        .options(joinedload(CentreTest.test))
        .filter(CentreTest.id == centre_test.id)
        .first()
    )


def get_centre_tests_by_ids(
    db: Session,
    centre_id: int,
    centre_test_ids: List[int],
) -> List[CentreTest]:
    return (
        db.query(CentreTest)
        .options(joinedload(CentreTest.test))
        .filter(
            CentreTest.centre_id == centre_id,
            CentreTest.id.in_(centre_test_ids),
            CentreTest.is_available.is_(True),
        )
        .all()
    )
