from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.centre_repo import CentreRepository
from app.utils.logger import logger
from app.utils.cache import catalogue_cache

class CentreService:
    def __init__(self, db: Session):
        self.centre_repo = CentreRepository(db)

    def get_all_centres(self):
        cached_data = catalogue_cache.get("all_centres")
        if cached_data:
            logger.debug("Serving catalogue from in-memory SimpleCache")
            return cached_data

        logger.debug("Cache miss: Fetching all diagnostic centres from database")
        centres = self.centre_repo.get_all()
        
        catalogue_cache.set("all_centres", centres)
        return centres

    def get_centre_details(self, centre_id: int):
        cache_key = f"centre_detail_{centre_id}"
        
        cached_data = catalogue_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Serving centre_id={centre_id} from in-memory SimpleCache")
            return cached_data

        logger.debug(f"Cache miss: Fetching details for centre_id={centre_id} from database")
        centre = self.centre_repo.get_by_id(centre_id)
        
        if not centre:
            logger.warning(f"Centre lookup failed: centre_id={centre_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnostic centre not found."
            )
            
        catalogue_cache.set(cache_key, centre)
        return centre