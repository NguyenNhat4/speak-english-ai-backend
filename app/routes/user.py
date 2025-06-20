from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from typing import List

from app.schemas.user import UserCreate, UserResponse, UserUpdate, UserRegisterResponse, Token
from app.services.user_service import UserService
from app.utils.auth import get_current_user

router = APIRouter()

@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_create: UserCreate, user_service: UserService = Depends()):
    """
    Register a new user and return user info with an authentication token.
    """
    return user_service.register_user(user_create)

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), user_service: UserService = Depends()):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    return user_service.login_user(form_data.username, form_data.password)

@router.get("/me", response_model=UserResponse)
def get_user_profile(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends()
):
    """
    Get current user's profile.
    """
    user_id = str(current_user["_id"])
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/me", response_model=UserResponse)
def update_user_profile(user_update: UserUpdate, current_user: dict = Depends(get_current_user), user_service: UserService = Depends()):
    """
    Update current user's profile.
    """
    user_id = str(current_user["_id"])
    updated_user = user_service.update_user_profile(user_id, user_update)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return updated_user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_profile(current_user: dict = Depends(get_current_user), user_service: UserService = Depends()):
    """
    Delete current user's profile (soft delete).
    """
    user_id = str(current_user["_id"])
    deleted_user = user_service.delete_user(user_id)
    if not deleted_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return None

@router.get("/list", response_model=List[UserResponse])
def get_users(skip: int = 0, limit: int = 100, user_service: UserService = Depends(), current_user: dict = Depends(get_current_user)):
    """
    Get a list of users (for admin purposes).
    This endpoint should be protected and only accessible by admins.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access this endpoint"
        )
    users = user_service.user_repo.get_all_users(skip=skip, limit=limit)
    return users
