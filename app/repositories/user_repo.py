from sqlalchemy.orm import Session

from app.models.user import User


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()


def create_user(db: Session, user: User) -> User:
    db.add(user)
    db.flush()
    return user
