from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)

@router.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: schemas.UserCreate, service: AuthService = Depends(get_auth_service)):
    return service.signup(user_data)

@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service)
):
    return service.login(form_data)