"""
User Service for handling all user-related business logic.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from app.schemas.user import Token, UserResponse
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate, UserRegisterResponse
from app.utils.security import hash_password, verify_password
from app.utils.auth import create_access_token, oauth2_scheme
from app.config.settings import settings
from jose import jwt, JWTError, ExpiredSignatureError

logger = logging.getLogger(__name__)
logger.info("UserService initialized")

class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def get_users(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        """
        Get all users.
        """
        users = self.user_repo.get_all_users(skip=skip, limit=limit)
        return [UserResponse.model_validate(user) for user in users]

    def register_user(self, user_create: UserCreate) -> UserRegisterResponse:
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
        response_data.update(access_token.model_dump())
        return UserRegisterResponse.model_validate(response_data)

    def login_user(self, email: str, password: str) -> Token:
        """
        Authenticate a user and return an access token.
        """
        user_data = self.user_repo.get_user_by_email(email)
        if not user_data or not verify_password(password, user_data['password']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = UserResponse.model_validate(user_data)
        return self.create_auth_token(user.email, user.role)

    def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """
        Get a user by their ID.
        """
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return UserResponse.model_validate(user)

    def update_user_profile(self, user_id: str, user_update: UserUpdate) -> Optional[UserResponse]:
        """
        Update a user's profile.
        """
        update_data = user_update.model_dump(exclude_unset=True)
        updated_user = self.user_repo.update_user(user_id, update_data)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return UserResponse.model_validate(updated_user)

    def delete_user(self, user_id: str) -> Optional[UserResponse]:
        """
        Soft delete a user.
        """
        deleted_user = self.user_repo.delete_user(user_id)
        if not deleted_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return UserResponse.model_validate(deleted_user)

    def create_auth_token(self, email: str, role: str = "user") -> Token:
        """
        Create an authentication token for a user.
        """
        scopes = ["admin"] if role == "admin" else ["user"]
        access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": email, "scopes": scopes},
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            scope=" ".join(scopes)
        )

    def get_user_from_token(self, token: Optional[str], required_scopes: List[str] = []) -> UserResponse:
        """
        Decode the JWT token, validate scopes, and return the user.
        This is a regular method, not a dependency.
        """
        authenticate_value = f'Bearer scope="{ " ".join(required_scopes)}"'
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
        
        if token is None:
            raise credentials_exception

        try:
            payload = jwt.decode(token, settings.get_secret_key(), algorithms=[settings.jwt_algorithm])
            email = payload.get("sub")
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
        
        user_data = self.user_repo.get_user_by_email(email)
        if user_data is None:
            raise credentials_exception
            
        for scope in required_scopes:
            if scope not in token_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions",
                    headers={"WWW-Authenticate": authenticate_value},
                )
        
        return UserResponse.model_validate(user_data) 