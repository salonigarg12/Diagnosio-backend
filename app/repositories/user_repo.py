from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, name: str, email: str, password_hash: str) -> User:
        new_user = User(
            name=name,
            email=email,
            password_hash=password_hash
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user