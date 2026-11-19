import os
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "diagnosio-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(
    user_id: int,
    email: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT carrying user_id, email, and RBAC role claims."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT, raising JWTError on failure."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
