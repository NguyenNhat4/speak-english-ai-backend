"""
Conversation Repository Implementation

This module provides specialized repository operations for conversation data,
extending the base repository with conversation-specific methods.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.repositories.base_repository import BaseRepository
from app.models.conversation import Conversation

logger = logging.getLogger(__name__)


class ConversationRepository(BaseRepository[Conversation]):
    """
    Repository class for handling conversation database operations.
    
    This class extends BaseRepository to provide conversation-specific
    database operations while maintaining consistency with the repository pattern.
    """
    
    def __init__(self):
        """Initialize the conversation repository."""
        super().__init__("conversations", Conversation)
    
    def create_conversation(self, user_id: str, user_role: str, ai_role: str, 
                          situation: str, voice_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new conversation.
        
        Args:
            user_id: String representation of the user ID
            user_role: Role of the user in the conversation
            ai_role: Role of the AI in the conversation
            situation: Description of the conversation situation
            voice_type: Optional voice type preference
            
        Returns:
            Created conversation document
            
        Raises:
            HTTPException: If creation fails
        """
        try:
            # Convert user_id to ObjectId
            user_object_id = ObjectId(user_id)
            
            # Create conversation model instance
            conversation = Conversation(
                user_id=user_object_id,
                user_role=user_role,
                ai_role=ai_role,
                situation=situation,
                voice_type=voice_type
            )
            
            # Use base repository create method
            return self.create(conversation.to_dict())
            
        except Exception as e:
            self.logger.error(f"Error creating conversation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create conversation: {str(e)}"
            )
    
    def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by its ID.
        
        Args:
            conversation_id: String representation of the conversation ID
            
        Returns:
            Conversation document if found, None otherwise
        """
        return self.find_by_id(conversation_id)
    
    def get_user_conversations(self, user_id: str, skip: int = 0, 
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all conversations for a specific user.
        
        Args:
            user_id: String representation of the user ID
            skip: Number of conversations to skip for pagination
            limit: Maximum number of conversations to return
            
        Returns:
            List of user's conversations
            
        Raises:
            HTTPException: If user_id is invalid or query fails
        """
        try:
            # Convert user_id to ObjectId
            user_object_id = ObjectId(user_id)
            
            # Build filter for user's conversations
            filter_dict = {"user_id": user_object_id}
            
            # Sort by most recent first
            sort = [("started_at", -1)]
            
            return self.find_all(
                filter_dict=filter_dict,
                skip=skip,
                limit=limit,
                sort=sort
            )
            
        except Exception as e:
            self.logger.error(f"Error getting user conversations: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user ID or query failed: {str(e)}"
            )
    
    def get_active_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active (not ended) conversations for a user.
        
        Args:
            user_id: String representation of the user ID
            
        Returns:
            List of active conversations
        """
        try:
            # Convert user_id to ObjectId
            user_object_id = ObjectId(user_id)
            
            # Filter for active conversations (ended_at is None)
            filter_dict = {
                "user_id": user_object_id,
                "ended_at": None
            }
            
            # Sort by most recent first
            sort = [("started_at", -1)]
            
            return self.find_all(filter_dict=filter_dict, sort=sort)
            
        except Exception as e:
            self.logger.error(f"Error getting active conversations: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user ID or query failed: {str(e)}"
            )
    
    def end_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Mark a conversation as ended.
        
        Args:
            conversation_id: String representation of the conversation ID
            
        Returns:
            Updated conversation document if found, None otherwise
        """
        try:
            update_data = {
                "ended_at": datetime.utcnow()
            }
            
            return self.update(conversation_id, update_data)
            
        except Exception as e:
            self.logger.error(f"Error ending conversation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to end conversation: {str(e)}"
            )
    
    def update_conversation_metadata(self, conversation_id: str, 
                                   metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update conversation metadata.
        
        Args:
            conversation_id: String representation of the conversation ID
            metadata: Dictionary containing metadata to update
            
        Returns:
            Updated conversation document if found, None otherwise
        """
        return self.update(conversation_id, metadata)
    
    def get_conversations_by_situation(self, situation: str, user_id: Optional[str] = None,
                                     skip: int = 0, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get conversations by situation type.
        
        Args:
            situation: The situation to filter by
            user_id: Optional user ID to filter by specific user
            skip: Number of conversations to skip for pagination
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversations matching the situation
        """
        try:
            # Build filter
            filter_dict = {"situation": {"$regex": situation, "$options": "i"}}
            
            # Add user filter if provided
            if user_id:
                user_object_id = ObjectId(user_id)
                filter_dict["user_id"] = user_object_id
            
            # Sort by most recent first
            sort = [("started_at", -1)]
            
            return self.find_all(
                filter_dict=filter_dict,
                skip=skip,
                limit=limit,
                sort=sort
            )
            
        except Exception as e:
            self.logger.error(f"Error getting conversations by situation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get conversations by situation: {str(e)}"
            )
    
    def get_conversation_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get conversation statistics for a user.
        
        Args:
            user_id: String representation of the user ID
            
        Returns:
            Dictionary containing conversation statistics
        """
        try:
            # Convert user_id to ObjectId
            user_object_id = ObjectId(user_id)
            
            # Total conversations
            total_count = self.count({"user_id": user_object_id})
            
            # Active conversations
            active_count = self.count({
                "user_id": user_object_id,
                "ended_at": None
            })
            
            # Completed conversations
            completed_count = self.count({
                "user_id": user_object_id,
                "ended_at": {"$ne": None}
            })
            
            return {
                "total_conversations": total_count,
                "active_conversations": active_count,
                "completed_conversations": completed_count
            }
            
        except Exception as e:
            self.logger.error(f"Error getting conversation statistics: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get conversation statistics: {str(e)}"
            ) 