"""
User Service for handling all user-related business logic.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.utils.security import hash_password, verify_password
from app.utils.auth import create_access_token, oauth2_scheme
from app.config.settings import settings
from jose import jwt, JWTError, ExpiredSignatureError

logger = logging.getLogger(__name__)
logger.info("UserService initialized")

class UserService:
    def __init__(self, user_repo: Optional[UserRepository] = None):
        self.user_repo = user_repo or UserRepository()

    def get_users(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all users.
        """
        return self.user_repo.get_all_users(skip=skip, limit=limit)

    def register_user(self, user_create: UserCreate) -> Dict[str, Any]:
        """
        Register a new user, hash their password, and create an access token.
        """
        existing_user = self.user_repo.get_user_by_email(user_create.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        hashed_password = hash_password(user_create.password)
        
        created_user = self.user_repo.create_user(
            name=user_create.name,
            email=user_create.email,
            password_hash=hashed_password
        )
        
        access_token = self.create_auth_token(created_user['email'])
        
        # Combine user data with token for the response
        response_data = created_user.copy()
        response_data.update(access_token)
        return response_data

    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user and return an access token.
        """
        user = self.user_repo.get_user_by_email(email)
        if not user or not verify_password(password, user['password']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return self.create_auth_token(user['email'], user['role'])

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by their ID.
        """
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

    def update_user_profile(self, user_id: str, user_update: UserUpdate) -> Optional[Dict[str, Any]]:
        """
        Update a user's profile.
        """
        update_data = user_update.dict(exclude_unset=True)
        updated_user = self.user_repo.update_user(user_id, update_data)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return updated_user

    def delete_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Soft delete a user.
        """
        deleted_user = self.user_repo.delete_user(user_id)
        if not deleted_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return deleted_user

    def create_auth_token(self, email: str, role: str = "user") -> Dict[str, Any]:
        """
        Create an authentication token for a user.
        """
        scopes = ["admin"] if role == "admin" else ["user"]
        access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": email, "scopes": scopes},
            expires_delta=access_token_expires
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "scope": " ".join(scopes)
        }

    def get_current_active_user(self, token: str, security_scopes: List[str]):
        authenticate_value = f'Bearer scope="{ " ".join(security_scopes)}"'
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
        
        try:
            payload = jwt.decode(token, settings.get_secret_key(), algorithms=[settings.jwt_algorithm])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
            token_scopes = payload.get("scopes", [])
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": authenticate_value},
            )
        except JWTError:
            raise credentials_exception
        
        user = self.user_repo.get_user_by_email(email)
        if user is None:
            raise credentials_exception
            
        for scope in security_scopes:
            if scope not in token_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions",
                    headers={"WWW-Authenticate": authenticate_value},
                )
        
        return user 