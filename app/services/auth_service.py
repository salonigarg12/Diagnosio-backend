from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import user_repo
from app.schemas import TokenResponse, UserLoginRequest, UserRegisterRequest
from app.utils.logger import get_logger
from app.utils.security import create_access_token, hash_password, verify_password

logger = get_logger(__name__)


def register_user(db: Session, payload: UserRegisterRequest) -> TokenResponse:
    """Register a new PATIENT or CENTRE_ADMIN and return a signed JWT response."""
    normalized_email = payload.email.lower()
    existing = user_repo.get_by_email(db, normalized_email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    try:
        user = User(
            full_name=payload.full_name.strip(),
            email=normalized_email,
            hashed_password=hash_password(payload.password),
            role=payload.role,
        )
        user_repo.create_user(db, user)
        db.commit()
        db.refresh(user)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to register user: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to complete registration.",
        )

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
    )


def login_user(db: Session, payload: UserLoginRequest) -> TokenResponse:
    """Authenticate credentials and issue a JWT containing user_id and role."""
    user = user_repo.get_by_email(db, payload.email.lower())
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
    )
