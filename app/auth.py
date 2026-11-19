from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.constants.enums import UserRole
from app.database import get_db
from app.models.user import User
from app.repositories import user_repo
from app.utils.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the Bearer JWT and return the authenticated User."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_repo.get_by_id(db, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )

    return user


def require_centre_admin(current_user: User = Depends(get_current_user)) -> User:
    """RBAC guard allowing only CENTRE_ADMIN users; raises 403 Forbidden for PATIENTs."""
    if current_user.role != UserRole.CENTRE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Diagnostic Centre Admin role is required.",
        )
    return current_user


def require_patient(current_user: User = Depends(get_current_user)) -> User:
    """RBAC guard allowing only PATIENT users; raises 403 Forbidden for CENTRE_ADMINs."""
    if current_user.role != UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Patient role is required.",
        )
    return current_user
