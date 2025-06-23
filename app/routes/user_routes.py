from fastapi import APIRouter, Depends, status, HTTPException, Security
from fastapi.security import OAuth2PasswordRequestForm
from typing import List

from app.schemas.user import UserCreate, UserResponse, UserUpdate, UserRegisterResponse, Token
from app.services.user_service import UserService
from app.services import provider
from app.utils.auth import get_current_active_user, get_current_admin_user

router = APIRouter()

@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_create: UserCreate, user_service: UserService = Depends(provider.get_user_service)):
    """
    Register a new user and return user info with an authentication token.
    """
    return user_service.register_user(user_create)

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), user_service: UserService = Depends(provider.get_user_service)):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    return user_service.login_user(form_data.username, form_data.password)

@router.get("/me", response_model=UserResponse)
async def get_user_profile(
    current_user: UserResponse = Security(get_current_active_user, scopes=["user"])
):
    """
    Get current user's profile.
    """
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    user_update: UserUpdate, 
    current_user: UserResponse = Security(get_current_active_user, scopes=["user"]),
    user_service: UserService = Depends(provider.get_user_service)
):
    """
    Update current user's profile.
    """
    user_id = str(current_user.id)
    return user_service.update_user_profile(user_id, user_update)

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_profile(
    current_user: UserResponse = Security(get_current_active_user, scopes=["user"]),
    user_service: UserService = Depends(provider.get_user_service)
):
    """
    Delete current user's profile (soft delete).
    """
    user_id = str(current_user.id)
    user_service.delete_user(user_id)
    return None

@router.get("/list", response_model=List[UserResponse])
def get_users(
    skip: int = 0, 
    limit: int = 100, 
    user_service: UserService = Depends(provider.get_user_service), 
    admin_user: UserResponse = Depends(get_current_admin_user)
):
    """
    Get a list of users (for admin purposes).
    """
    return user_service.get_users(skip=skip, limit=limit) 