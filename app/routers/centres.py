from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import schemas, models
from app.repositories.centre_repo import CentreRepository
from app.utils.cache import catalogue_cache

router = APIRouter(prefix="/centres", tags=["Centres & Tests"])

@router.get("/", response_model=List[schemas.CentreResponse])
def get_centres(db: Session = Depends(get_db)):
    cached_data = catalogue_cache.get("centres_list")
    if cached_data:
        return cached_data
    repo = CentreRepository(db)
    centres = repo.get_all()
    catalogue_cache.set("centres_list", centres, ttl=180)
    return centres

@router.get("/{centre_id}", response_model=schemas.CentreDetailResponse)
def get_centre_details(centre_id: int, db: Session = Depends(get_db)):
    repo = CentreRepository(db)
    centre = repo.get_by_id(centre_id)
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found.")
    
    centre_tests = db.query(models.CentreTest).filter(models.CentreTest.centre_id == centre_id).all()
    tests = [
        schemas.TestResponse(
            id=ct.test.id,
            name=ct.test.name,
            description=ct.test.description,
            price=ct.price
        )
        for ct in centre_tests
    ]
    return schemas.CentreDetailResponse(id=centre.id, name=centre.name, location=centre.location, tests=tests)