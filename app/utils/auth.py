from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import jwt, JWTError, ExpiredSignatureError
from typing import Optional
from app.config.database import db
from app.config.settings import settings
from bson import ObjectId
from app.services import provider
from app.services.user_service import UserService
from app.schemas.user import UserResponse as User

# OAuth2 scheme for token authentication (points to the login endpoint)
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/users/login",
    scopes={"user": "Read user information", "admin": "Full access"}
)



def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Generate a JWT access token with an expiration time.
    
    Args:
        data (dict): Dictionary containing the data to encode in the token.
            Sample input:
            {
                "sub": "user@example.com"  # user email
            }
        expires_delta (Optional[timedelta], optional): Custom expiration time for the token.
            If not provided, defaults to ACCESS_TOKEN_EXPIRE_MINUTES.
    
    Returns:
        str: The encoded JWT token.
            Sample output:
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyQGV4YW1wbGUuY29tIiwiZXhwIjoxNzEyMjI0MDAwfQ.xyz..."
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.get_secret_key(), algorithm=settings.jwt_algorithm)

def get_current_active_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(provider.get_user_service)
) -> User:
    if security_scopes.scopes:
        user_data = user_service.get_current_active_user(token, security_scopes.scopes)
        return User(**user_data)
    user_data = user_service.get_current_active_user(token, [])
    return User(**user_data)

def get_current_admin_user(
    user: User = Security(get_current_active_user, scopes=["admin"])
) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges"
        )
    return user