from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.repositories.user_repo import UserRepository
from app.utils.security import hash_password, verify_password, create_access_token
from app import schemas
from app.utils.logger import logger

class AuthService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def signup(self, user_data: schemas.UserCreate):
        logger.info(f"User signup initiated for email={user_data.email}")
        existing_user = self.user_repo.get_by_email(user_data.email)
        
        if existing_user:
            logger.warning(f"Signup conflict: Account already exists for email={user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered."
            )

        new_user = self.user_repo.create_user(
            name=user_data.name,
            email=user_data.email,
            password_hash=hash_password(user_data.password)
        )
        logger.info(f"User successfully registered: user_id={new_user.id}")
        return new_user

    def login(self, form_data: OAuth2PasswordRequestForm):
        logger.info(f"Authentication attempt for username={form_data.username}")
        user = self.user_repo.get_by_email(form_data.username)

        if not user or not verify_password(form_data.password, user.password_hash):
            logger.warning(f"Authentication failed: Invalid credentials for username={form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        token = create_access_token(data={"sub": str(user.id)})
        logger.info(f"Authentication successful for user_id={user.id}")
        return {"access_token": token, "token_type": "bearer"}