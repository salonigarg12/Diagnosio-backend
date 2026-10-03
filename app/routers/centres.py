from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.centre_service import CentreService

router = APIRouter(prefix="/centres", tags=["Centres"])

def get_centre_service(db: Session = Depends(get_db)) -> CentreService:
    return CentreService(db)

@router.get("/")
def list_centres(service: CentreService = Depends(get_centre_service)):
    return service.get_all_centres()

@router.get("/{centre_id}")
def get_centre(centre_id: int, service: CentreService = Depends(get_centre_service)):
    return service.get_centre_details(centre_id)