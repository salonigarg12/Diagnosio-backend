from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.centre_repo import CentreRepository
from app.utils.logger import logger

class CentreService:
    def __init__(self, db: Session):
        self.centre_repo = CentreRepository(db)

    def get_all_centres(self):
        logger.debug("Fetching all diagnostic centres from catalogue")
        # Note: If you are using the in-memory TTL cache (cache.py), wrap the call below with it.
        return self.centre_repo.get_all()

    def get_centre_details(self, centre_id: int):
        logger.debug(f"Fetching details for centre_id={centre_id}")
        centre = self.centre_repo.get_by_id(centre_id)
        
        if not centre:
            logger.warning(f"Centre lookup failed: centre_id={centre_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnostic centre not found."
            )
        return centre