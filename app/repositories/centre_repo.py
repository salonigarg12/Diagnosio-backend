from sqlalchemy.orm import Session
from app.models import Centre, CentreTest

class CentreRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self):
        return self.db.query(Centre).all()

    def get_by_id(self, centre_id: int):
        return self.db.query(Centre).filter(Centre.id == centre_id).first()

    def get_centre_tests(self, centre_id: int, test_ids: list[int]):
        return self.db.query(CentreTest).filter(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id.in_(test_ids)
        ).all()