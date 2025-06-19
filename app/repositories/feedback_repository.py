"""
Feedback Repository Implementation

This module provides specialized repository operations for feedback data,
extending the base repository with feedback-specific methods.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import HTTPException

from app.repositories.base_repository import BaseRepository
from app.models.feedback import Feedback

logger = logging.getLogger(__name__)


class FeedbackRepository(BaseRepository[Feedback]):
    """
    Repository class for handling feedback database operations.
    
    This class extends BaseRepository to provide feedback-specific
    database operations while maintaining consistency with the repository pattern.
    """
    
    def __init__(self):
        """Initialize the feedback repository."""
        super().__init__("feedback", Feedback)
    
    def create_feedback(self, target_id: str, target_type: str, user_feedback: str,
                       user_id: Optional[str] = None, transcription: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new feedback entry.
        
        Args:
            target_id: ID of the entity receiving feedback
            target_type: Type of entity ("message", "audio", etc.)
            user_feedback: User-friendly feedback text
            user_id: Optional user ID providing feedback
            transcription: Optional transcription being analyzed
            
        Returns:
            Created feedback document
            
        Raises:
            HTTPException: If creation fails
        """
        try:
            # Convert string IDs to ObjectId
            target_object_id = ObjectId(target_id)
            user_object_id = ObjectId(user_id) if user_id else None
            
            # Create feedback model instance
            feedback = Feedback(
                target_id=target_object_id,
                target_type=target_type,
                user_feedback=user_feedback,
                user_id=user_object_id,
                transcription=transcription
            )
            
            # Use base repository create method
            return self.create(feedback.to_dict())
            
        except Exception as e:
            self.logger.error(f"Error creating feedback: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create feedback: {str(e)}"
            )
    
    def get_feedback_by_target(self, target_id: str, target_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all feedback for a specific target.
        
        Args:
            target_id: String representation of the target ID
            target_type: Optional target type filter
            
        Returns:
            List of feedback entries for the target
        """
        try:
            # Convert target_id to ObjectId
            target_object_id = ObjectId(target_id)
            
            # Build filter
            filter_dict = {"target_id": target_object_id}
            if target_type:
                filter_dict["target_type"] = target_type
            
            # Sort by most recent first
            sort = [("timestamp", -1)]
            
            return self.find_all(filter_dict=filter_dict, sort=sort)
            
        except Exception as e:
            self.logger.error(f"Error getting feedback by target: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid target ID or query failed: {str(e)}"
            )
    
    def get_feedback_by_user(self, user_id: str, skip: int = 0, 
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all feedback provided by a specific user.
        
        Args:
            user_id: String representation of the user ID
            skip: Number of feedback entries to skip for pagination
            limit: Maximum number of feedback entries to return
            
        Returns:
            List of feedback entries by the user
        """
        try:
            # Convert user_id to ObjectId
            user_object_id = ObjectId(user_id)
            
            # Build filter
            filter_dict = {"user_id": user_object_id}
            
            # Sort by most recent first
            sort = [("timestamp", -1)]
            
            return self.find_all(
                filter_dict=filter_dict,
                skip=skip,
                limit=limit,
                sort=sort
            )
            
        except Exception as e:
            self.logger.error(f"Error getting feedback by user: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user ID or query failed: {str(e)}"
            )
 