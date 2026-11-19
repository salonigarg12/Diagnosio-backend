from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas import TokenResponse, UserLoginRequest, UserRegisterRequest, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Register a new PATIENT or CENTRE_ADMIN account."""
    return auth_service.register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate an existing user and return a JWT with role and user_id."""
    return auth_service.login_user(db, payload)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)
