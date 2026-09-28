from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])

@router.get("/", response_model=List[schemas.CentreResponse])
def get_centres(db: Session = Depends(get_db)):
    # SELECT * FROM centres;
    centres = db.query(models.DiagnosticCentre).all()
    return centres

@router.get("/{centre_id}", response_model=schemas.CentreDetailResponse)
def get_centre_details(centre_id: int, db: Session = Depends(get_db)):
    # 1. Fetch the diagnostic centre
    centre = db.query(models.DiagnosticCentre).filter(models.DiagnosticCentre.id == centre_id).first()
    if not centre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic centre with id {centre_id} not found"
        )

    # 2. Fetch all tests linked to this centre with their prices
    centre_tests = db.query(models.CentreTest).filter(models.CentreTest.centre_id == centre_id).all()
    
    available_tests = []
    for ct in centre_tests:
        available_tests.append(
            schemas.TestBase(
                id=ct.test.id,
                name=ct.test.name,
                description=ct.test.description,
                price=ct.price
            )
        )

    return schemas.CentreDetailResponse(
        id=centre.id,
        name=centre.name,
        location=centre.location,
        available_tests=available_tests
    )