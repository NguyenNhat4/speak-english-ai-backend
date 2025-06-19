"""
Message Repository Implementation

This module provides specialized repository operations for message data,
extending the base repository with message-specific methods.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.repositories.base_repository import BaseRepository
from app.models.message import Message

logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository[Message]):
    """
    Repository class for handling message database operations.
    
    This class extends BaseRepository to provide message-specific
    database operations while maintaining consistency with the repository pattern.
    """
    
    def __init__(self):
        """Initialize the message repository."""
        super().__init__("messages", Message)
    
    def create_message(self, conversation_id: str, sender: str, content: str,
                      audio_path: Optional[str] = None, transcription: Optional[str] = None,
                      feedback_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new message.
        
        Args:
            conversation_id: String representation of the conversation ID
            sender: Message sender ("user" or "ai")
            content: Message content
            audio_path: Optional path to audio file
            transcription: Optional transcription of audio
            feedback_id: Optional feedback ID
            
        Returns:
            Created message document
            
        Raises:
            HTTPException: If creation fails
        """
        try:
            # Convert conversation_id to ObjectId
            conversation_object_id = ObjectId(conversation_id)
            
            # Create message model instance
            message = Message(
                conversation_id=conversation_object_id,
                sender=sender,
                content=content,
                audio_path=audio_path,
                transcription=transcription,
                feedback_id=feedback_id
            )
            
            # Use base repository create method
            return self.create(message.to_dict())
            
        except Exception as e:
            self.logger.error(f"Error creating message: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create message: {str(e)}"
            )
    
    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a message by its ID.
        
        Args:
            message_id: String representation of the message ID
            
        Returns:
            Message document if found, None otherwise
        """
        return self.find_by_id(message_id)
    
    def get_messages_by_conversation(self, conversation_id: str, skip: int = 0,
                                   limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all messages for a specific conversation.
        
        Args:
            conversation_id: String representation of the conversation ID
            skip: Number of messages to skip for pagination
            limit: Maximum number of messages to return
            
        Returns:
            List of messages in the conversation
            
        Raises:
            HTTPException: If conversation_id is invalid or query fails
        """
        try:
            # Convert conversation_id to ObjectId
            conversation_object_id = ObjectId(conversation_id)
            
            # Build filter for conversation's messages
            filter_dict = {"conversation_id": conversation_object_id}
            
            # Sort by timestamp (oldest first for conversation flow)
            sort = [("timestamp", 1)]
            
            return self.find_all(
                filter_dict=filter_dict,
                skip=skip,
                limit=limit,
                sort=sort
            )
            
        except Exception as e:
            self.logger.error(f"Error getting conversation messages: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid conversation ID or query failed: {str(e)}"
            )
    
    def get_user_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all user messages from a conversation.
        
        Args:
            conversation_id: String representation of the conversation ID
            
        Returns:
            List of user messages
        """
        try:
            # Convert conversation_id to ObjectId
            conversation_object_id = ObjectId(conversation_id)
            
            # Filter for user messages only
            filter_dict = {
                "conversation_id": conversation_object_id,
                "sender": "user"
            }
            
            # Sort by timestamp
            sort = [("timestamp", 1)]
            
            return self.find_all(filter_dict=filter_dict, sort=sort)
            
        except Exception as e:
            self.logger.error(f"Error getting user messages: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid conversation ID or query failed: {str(e)}"
            )
    
    def get_ai_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all AI messages from a conversation.
        
        Args:
            conversation_id: String representation of the conversation ID
            
        Returns:
            List of AI messages
        """
        try:
            # Convert conversation_id to ObjectId
            conversation_object_id = ObjectId(conversation_id)
            
            # Filter for AI messages only
            filter_dict = {
                "conversation_id": conversation_object_id,
                "sender": "ai"
            }
            
            # Sort by timestamp
            sort = [("timestamp", 1)]
            
            return self.find_all(filter_dict=filter_dict, sort=sort)
            
        except Exception as e:
            self.logger.error(f"Error getting AI messages: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid conversation ID or query failed: {str(e)}"
            )
    
    def update_message_feedback(self, message_id: str, feedback_id: str) -> Optional[Dict[str, Any]]:
        """
        Update a message with feedback ID.
        
        Args:
            message_id: String representation of the message ID
            feedback_id: String representation of the feedback ID
            
        Returns:
            Updated message document if found, None otherwise
        """
        try:
            update_data = {
                "feedback_id": feedback_id
            }
            
            return self.update(message_id, update_data)
            
        except Exception as e:
            self.logger.error(f"Error updating message feedback: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update message feedback: {str(e)}"
            )
    
    def update_message_transcription(self, message_id: str, transcription: str) -> Optional[Dict[str, Any]]:
        """
        Update a message with transcription.
        
        Args:
            message_id: String representation of the message ID
            transcription: Transcription text
            
        Returns:
            Updated message document if found, None otherwise
        """
        try:
            update_data = {
                "transcription": transcription
            }
            
            return self.update(message_id, update_data)
            
        except Exception as e:
            self.logger.error(f"Error updating message transcription: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update message transcription: {str(e)}"
            )
    
    def get_messages_with_audio(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages with audio from a conversation.
        
        Args:
            conversation_id: String representation of the conversation ID
            
        Returns:
            List of messages that have audio
        """
        try:
            # Convert conversation_id to ObjectId
            conversation_object_id = ObjectId(conversation_id)
            
            # Filter for messages with audio
            filter_dict = {
                "conversation_id": conversation_object_id,
                "audio_path": {"$ne": None, "$exists": True}
            }
            
            # Sort by timestamp
            sort = [("timestamp", 1)]
            
            return self.find_all(filter_dict=filter_dict, sort=sort)
            
        except Exception as e:
            self.logger.error(f"Error getting messages with audio: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid conversation ID or query failed: {str(e)}"
            )
    
    def get_messages_with_feedback(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages with feedback from a conversation.
        
        Args:
            conversation_id: String representation of the conversation ID
            
        Returns:
            List of messages that have feedback
        """
        try:
            # Convert conversation_id to ObjectId
            conversation_object_id = ObjectId(conversation_id)
            
            # Filter for messages with feedback
            filter_dict = {
                "conversation_id": conversation_object_id,
                "feedback_id": {"$ne": None, "$exists": True}
            }
            
            # Sort by timestamp
            sort = [("timestamp", 1)]
            
            return self.find_all(filter_dict=filter_dict, sort=sort)
            
        except Exception as e:
            self.logger.error(f"Error getting messages with feedback: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid conversation ID or query failed: {str(e)}"
            )
    
    def get_latest_message(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest message from a conversation.
        
        Args:
            conversation_id: String representation of the conversation ID
            
        Returns:
            Latest message document if found, None otherwise
        """
        try:
            # Convert conversation_id to ObjectId
            conversation_object_id = ObjectId(conversation_id)
            
            # Build filter for conversation's messages
            filter_dict = {"conversation_id": conversation_object_id}
            
            # Sort by timestamp (latest first) and limit to 1
            sort = [("timestamp", -1)]
            
            messages = self.find_all(
                filter_dict=filter_dict,
                limit=1,
                sort=sort
            )
            
            return messages[0] if messages else None
            
        except Exception as e:
            self.logger.error(f"Error getting latest message: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid conversation ID or query failed: {str(e)}"
            )
    
    def get_message_statistics(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get message statistics for a conversation.
        
        Args:
            conversation_id: String representation of the conversation ID
            
        Returns:
            Dictionary containing message statistics
        """
        try:
            # Convert conversation_id to ObjectId
            conversation_object_id = ObjectId(conversation_id)
            
            # Total messages
            total_count = self.count({"conversation_id": conversation_object_id})
            
            # User messages
            user_count = self.count({
                "conversation_id": conversation_object_id,
                "sender": "user"
            })
            
            # AI messages
            ai_count = self.count({
                "conversation_id": conversation_object_id,
                "sender": "ai"
            })
            
            # Messages with audio
            audio_count = self.count({
                "conversation_id": conversation_object_id,
                "audio_path": {"$ne": None, "$exists": True}
            })
            
            # Messages with feedback
            feedback_count = self.count({
                "conversation_id": conversation_object_id,
                "feedback_id": {"$ne": None, "$exists": True}
            })
            
            return {
                "total_messages": total_count,
                "user_messages": user_count,
                "ai_messages": ai_count,
                "messages_with_audio": audio_count,
                "messages_with_feedback": feedback_count
            }
            
        except Exception as e:
            self.logger.error(f"Error getting message statistics: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get message statistics: {str(e)}"
            ) 