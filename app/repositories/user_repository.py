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
    
    def create_user(self, name: str, email: str, password_hash: str) -> Dict[str, Any]:
        """
        Create a new user.
        
        Args:
            name: User's full name
            email: User's email address
            password_hash: Hashed password
            
        Returns:
            Created user document
        """
        try:
            # Create user model instance
            user = User(
                name=name,
                email=email,
                password_hash=password_hash
            )
            
            # Use base repository create method
            return self.create(user.to_dict())
        except Exception as e:
            self.logger.error(f"Error creating user in repository: {str(e)}")
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
            return self.find_one({"email": email})
        except Exception as e:
            self.logger.error(f"Error getting user by email: {str(e)}")
            return None
            
    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update a user's data.
        
        Args:
            user_id: String representation of the user ID
            update_data: Dictionary containing fields to update
            
        Returns:
            Updated user document if found, None otherwise
        """
        try:
            return self.update(user_id, update_data)
        except Exception as e:
            self.logger.error(f"Error updating user profile: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update user profile: {str(e)}"
            )
    
    def delete_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Soft delete a user by setting 'is_deleted' to True.
        
        Args:
            user_id: String representation of the user ID
            
        Returns:
            The updated user document if found, None otherwise
        """
        try:
            delete_data = {
                "is_deleted": True,
                "deleted_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            return self.update(user_id, delete_data)
        except Exception as e:
            self.logger.error(f"Error deleting user: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete user: {str(e)}"
            )
    
    def get_all_users(self, skip: int = 0, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all users with pagination.
        
        Args:
            skip: Number of users to skip for pagination
            limit: Maximum number of users to return
            
        Returns:
            List of user documents
        """
        try:
            # Sort by creation date (newest first)
            sort = [("created_at", -1)]
            
            return self.find_all(
                filter_dict={},
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