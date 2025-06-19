"""
Mistake Repository Implementation

This module provides specialized repository operations for mistake tracking data,
extending the base repository with mistake-specific methods.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import HTTPException

from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class MistakeRepository(BaseRepository):
    """
    Repository class for handling mistake tracking database operations.
    
    This class extends BaseRepository to provide mistake-specific
    database operations while maintaining consistency with the repository pattern.
    """
    
    def __init__(self):
        """Initialize the mistake repository."""
        super().__init__("mistakes", dict)
    
    def create_mistake(self, user_id: str, mistake_type: str, original_text: str, 
                      correction: str, explanation: str, context: str = None) -> Dict[str, Any]:
        """
        Create a new mistake entry.
        
        Args:
            user_id: String representation of the user ID
            mistake_type: Type of mistake (GRAMMAR, VOCABULARY, etc.)
            original_text: Original incorrect text
            correction: Corrected text
            explanation: Explanation of the mistake
            context: Optional context where mistake occurred
            
        Returns:
            Created mistake document
        """
        try:
            # Convert user_id to ObjectId
            user_object_id = ObjectId(user_id)
            
            mistake_data = {
                "user_id": user_object_id,
                "type": mistake_type,
                "original_text": original_text,
                "correction": correction,
                "explanation": explanation,
                "context": context,
                "status": "NEW",
                "confidence_level": 0,
                "in_drill_queue": True,
                "next_practice_date": datetime.utcnow(),
                "practice_count": 0,
                "consecutive_correct": 0,
                "last_practiced": None
            }
            
            return self.create(mistake_data)
            
        except Exception as e:
            self.logger.error(f"Error creating mistake: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create mistake: {str(e)}"
            )
    
    def get_user_mistakes(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all mistakes for a user, optionally filtered by status.
        
        Args:
            user_id: String representation of the user ID
            status: Optional status filter
            
        Returns:
            List of user's mistakes
        """
        try:
            user_object_id = ObjectId(user_id)
            
            filter_dict = {"user_id": user_object_id}
            if status:
                filter_dict["status"] = status
            
            sort = [("created_at", -1)]
            
            return self.find_all(filter_dict=filter_dict, sort=sort)
            
        except Exception as e:
            self.logger.error(f"Error getting user mistakes: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user ID or query failed: {str(e)}"
            )
    
    def get_mistakes_for_practice(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get mistakes due for practice using spaced repetition.
        
        Args:
            user_id: String representation of the user ID
            limit: Maximum number of mistakes to return
            
        Returns:
            List of mistakes due for practice
        """
        try:
            user_object_id = ObjectId(user_id)
            
            filter_dict = {
                "user_id": user_object_id,
                "in_drill_queue": True,
                "next_practice_date": {"$lte": datetime.utcnow()}
            }
            
            sort = [("next_practice_date", 1)]
            
            return self.find_all(filter_dict=filter_dict, limit=limit, sort=sort)
            
        except Exception as e:
            self.logger.error(f"Error getting mistakes for practice: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user ID or query failed: {str(e)}"
            )
    
    def update_practice_result(self, mistake_id: str, correct: bool) -> Optional[Dict[str, Any]]:
        """
        Update mistake based on practice result.
        
        Args:
            mistake_id: String representation of the mistake ID
            correct: Whether the practice was correct
            
        Returns:
            Updated mistake document
        """
        try:
            mistake = self.find_by_id(mistake_id)
            if not mistake:
                return None
            
            # Update practice statistics
            practice_count = mistake.get("practice_count", 0) + 1
            consecutive_correct = mistake.get("consecutive_correct", 0)
            
            if correct:
                consecutive_correct += 1
                # Calculate next practice date based on spaced repetition
                days_to_add = min(consecutive_correct * 2, 30)  # Max 30 days
                next_practice = datetime.utcnow() + timedelta(days=days_to_add)
            else:
                consecutive_correct = 0
                next_practice = datetime.utcnow() + timedelta(hours=1)  # Retry soon
            
            # Determine status based on performance
            status = "MASTERED" if consecutive_correct >= 5 else "LEARNING"
            confidence_level = min(consecutive_correct * 20, 100)
            
            update_data = {
                "practice_count": practice_count,
                "consecutive_correct": consecutive_correct,
                "next_practice_date": next_practice,
                "last_practiced": datetime.utcnow(),
                "status": status,
                "confidence_level": confidence_level,
                "in_drill_queue": status != "MASTERED"
            }
            
            return self.update(mistake_id, update_data)
            
        except Exception as e:
            self.logger.error(f"Error updating practice result: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update practice result: {str(e)}"
            ) 