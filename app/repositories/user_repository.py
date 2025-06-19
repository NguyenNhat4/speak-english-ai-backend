"""
User Repository Implementation

This module provides specialized repository operations for user data,
extending the base repository with user-specific methods.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.repositories.base_repository import BaseRepository
from app.models.user import User

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """
    Repository class for handling user database operations.
    
    This class extends BaseRepository to provide user-specific
    database operations while maintaining consistency with the repository pattern.
    """
    
    def __init__(self):
        """Initialize the user repository."""
        super().__init__("users", User)
    
    def create_user(self, name: str, email: str, password_hash: str,
                   avatar_url: Optional[str] = None, role: str = "user") -> Dict[str, Any]:
        """
        Create a new user.
        
        Args:
            name: User's full name
            email: User's email address
            password_hash: Hashed password
            avatar_url: Optional avatar URL
            role: User role ("user" or "admin")
            
        Returns:
            Created user document
            
        Raises:
            HTTPException: If creation fails
        """
        try:
            # Create user model instance
            user = User(
                name=name,
                email=email,
                password_hash=password_hash,
                avatar_url=avatar_url,
                role=role
            )
            
            # Use base repository create method
            return self.create(user.to_dict())
            
        except Exception as e:
            self.logger.error(f"Error creating user: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create user: {str(e)}"
            )
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by their email address.
        
        Args:
            email: User's email address
            
        Returns:
            User document if found, None otherwise
        """
        try:
            filter_dict = {"email": email}
            users = self.find_all(filter_dict=filter_dict, limit=1)
            
            return users[0] if users else None
            
        except Exception as e:
            self.logger.error(f"Error getting user by email: {str(e)}")
            return None
    
    def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update user profile information.
        
        Args:
            user_id: String representation of the user ID
            profile_data: Dictionary containing profile fields to update
            
        Returns:
            Updated user document if found, None otherwise
        """
        try:
            # Remove sensitive fields that shouldn't be updated this way
            safe_fields = {
                "name": profile_data.get("name"),
                "avatar_url": profile_data.get("avatar_url")
            }
            
            # Remove None values
            update_data = {k: v for k, v in safe_fields.items() if v is not None}
            
            return self.update(user_id, update_data)
            
        except Exception as e:
            self.logger.error(f"Error updating user profile: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update user profile: {str(e)}"
            )
    
    def get_all_users(self, skip: int = 0, limit: Optional[int] = None,
                     include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        Get all users with pagination.
        
        Args:
            skip: Number of users to skip for pagination
            limit: Maximum number of users to return
            include_deleted: Whether to include soft-deleted users
            
        Returns:
            List of user documents
        """
        try:
            # Filter for non-deleted users unless requested
            filter_dict = {}
            if not include_deleted:
                filter_dict["deleted"] = {"$ne": True}
            
            # Sort by creation date (newest first)
            sort = [("created_at", -1)]
            
            return self.find_all(
                filter_dict=filter_dict,
                skip=skip,
                limit=limit,
                sort=sort
            )
            
        except Exception as e:
            self.logger.error(f"Error getting all users: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get users: {str(e)}"
            )