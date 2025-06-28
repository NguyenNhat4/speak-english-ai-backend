from fastapi import APIRouter, Depends, status, HTTPException, Security, Response
from fastapi.security import OAuth2PasswordRequestForm
from typing import List

from app.schemas.user import UserCreate, UserResponse, UserUpdate, UserRegisterResponse, Token
from app.services.user_service import UserService
from app.services.dependency_provider_service import DependencyProviderService

router = APIRouter()

@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_create: UserCreate, user_service: UserService = Depends(DependencyProviderService.get_user_service)) -> UserRegisterResponse:
    """
    Register a new user and return user info with an authentication token.
    """
    return user_service.register_user(user_create)

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), user_service: UserService = Depends(DependencyProviderService.get_user_service)):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    return user_service.login_user(form_data.username, form_data.password)

@router.get("/me", response_model=UserResponse)
async def get_user_profile(
    current_user: UserResponse = Security(DependencyProviderService.get_current_active_user, scopes=["user"])
) -> UserResponse:
    """
    Get the current user's profile information.
    """
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    user_update: UserUpdate, 
    current_user: UserResponse = Security(DependencyProviderService.get_current_active_user, scopes=["user"]),
    user_service: UserService = Depends(DependencyProviderService.get_user_service)
):
    """
    Update the current user's profile information.
    """
    return user_service.update_user_profile(current_user.id, user_update)

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_user_profile(
    current_user: UserResponse = Security(DependencyProviderService.get_current_active_user, scopes=["user"]),
    user_service: UserService = Depends(DependencyProviderService.get_user_service)
):
    """
    Delete the current user's account.
    """
    user_service.delete_user(current_user.id)

@router.get("/all", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0, 
    limit: int = 100, 
    user_service: UserService = Depends(DependencyProviderService.get_user_service), 
    admin_user: UserResponse = Security(DependencyProviderService.get_current_admin_user, scopes=["admin"])
):
    """
    Get all users. Admin access required.
    """
    return user_service.get_users(skip=skip, limit=limit) 