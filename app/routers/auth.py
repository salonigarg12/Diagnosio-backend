from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas, models
from app.utils.security import hash_password, verify_password, create_access_token
from app.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    logger.info(f"User signup initiated for email={user_data.email}")
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing_user:
        logger.warning(f"Signup conflict: Account already exists for email={user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered."
        )

    new_user = models.User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password(user_data.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"User successfully registered: user_id={new_user.id}")
    return new_user

@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    logger.info(f"Authentication attempt for username={form_data.username}")
    user = db.query(models.User).filter(models.User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        logger.warning(f"Authentication failed: Invalid credentials for username={form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = create_access_token(data={"sub": str(user.id)})
    logger.info(f"Authentication successful for user_id={user.id}")
    return {"access_token": token, "token_type": "bearer"}