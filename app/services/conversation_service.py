"""
Conversation Service for handling conversation-related business logic.

This service manages conversation creation, retrieval, and validation
for the SpeakAI application.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationCreate, ConversationResponse
from app.schemas.message import MessageResponse

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Service class for handling conversation business logic.
    
    This service encapsulates all conversation-related operations including
    creation, retrieval, validation, and management.
    """
    
    def __init__(self, conversation_repo: ConversationRepository = None, message_repo: MessageRepository = None):
        """
        Initialize the conversation service with repository dependencies.
        
        Args:
            conversation_repo: ConversationRepository instance
            message_repo: MessageRepository instance
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.conversation_repo = conversation_repo or ConversationRepository()
        self.message_repo = message_repo or MessageRepository()
    
    def create_conversation(
        self, 
        user_id: str, 
        refined_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new conversation with refined context and initial AI message.
        
        Args:
            user_id (str): The ID of the user creating the conversation
            refined_context (Dict[str, Any]): Refined conversation context from AI service
            
        Returns:
            Dict[str, Any]: Created conversation and initial message data
            
        Raises:
            HTTPException: If conversation creation fails
        """
        try:
            # Create conversation using repository
            conversation = self.conversation_repo.create_conversation(
                user_id=user_id,
                user_role=refined_context["refined_user_role"],
                ai_role=refined_context["refined_ai_role"],
                situation=refined_context["refined_situation"],
                voice_type=refined_context.get("voice_type")
            )
            
            conversation_id = str(conversation["_id"])
            
            # Create initial AI message using repository
            initial_message = self.message_repo.create_message(
                conversation_id=conversation_id,
                sender="ai",
                content=refined_context["response"]
            )
            
            # Prepare response data
            conversation_data = self._format_conversation_response(ObjectId(conversation_id))
            # Convert to message object for formatting
            message_obj = Message(
                conversation_id=ObjectId(conversation_id),
                sender="ai",
                content=refined_context["response"]
            )
            message_obj._id = ObjectId(initial_message["_id"])
            message_obj.timestamp = initial_message["timestamp"]
            message_data = self._format_message_response(message_obj, ObjectId(conversation_id))
            
            self.logger.info(f"Successfully created conversation {conversation_id} for user {user_id}")
            
            return {
                "conversation": ConversationResponse(**conversation_data),
                "initial_message": MessageResponse(**message_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create conversation for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create conversation: {str(e)}"
            )
    
    def get_conversation_context(self, conversation_id: str) -> Dict[str, Any]:
        """
        Retrieve conversation context and message history.
        
        Args:
            conversation_id (str): The ID of the conversation to retrieve
            
        Returns:
            Dict[str, Any]: Conversation data and message history
            
        Raises:
            HTTPException: If conversation not found or retrieval fails
        """
        try:
            # Validate and convert conversation ID
            if not ObjectId.is_valid(conversation_id):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid conversation ID format"
                )
            
            # Fetch conversation using repository
            conversation = self.conversation_repo.get_conversation_by_id(conversation_id)
            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found"
                )
            
            # Fetch messages for the conversation using repository
            messages = self.message_repo.get_messages_by_conversation(conversation_id)
            
            # Format message history for AI context
            history = [
                {
                    "role": "user" if msg["sender"] == "user" else "model",
                    "parts": [msg["content"]]
                }
                for msg in messages
            ]
            
            self.logger.debug(f"Retrieved conversation context for {conversation_id} with {len(messages)} messages")
            
            return {
                "conversation": conversation,
                "messages": messages,
                "history": history
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to retrieve conversation context for {conversation_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve conversation context: {str(e)}"
            )
    
    def validate_conversation_data(self, conversation_data: ConversationCreate) -> bool:
        """
        Validate conversation creation data.
        
        Args:
            conversation_data (ConversationCreate): The conversation data to validate
            
        Returns:
            bool: True if validation passes
            
        Raises:
            HTTPException: If validation fails
        """
        try:
            # Check required fields
            if not conversation_data.user_role or not conversation_data.user_role.strip():
                raise HTTPException(
                    status_code=400,
                    detail="User role is required and cannot be empty"
                )
            
            if not conversation_data.ai_role or not conversation_data.ai_role.strip():
                raise HTTPException(
                    status_code=400,
                    detail="AI role is required and cannot be empty"
                )
            
            if not conversation_data.situation or not conversation_data.situation.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Situation is required and cannot be empty"
                )
            
            # Validate length constraints
            if len(conversation_data.user_role) > 5:
                raise HTTPException(
                    status_code=400,
                    detail="User role must be 100 characters or less"
                )
            
            if len(conversation_data.ai_role) > 5:
                raise HTTPException(
                    status_code=400,
                    detail="AI role must be 100 characters or less"
                )
            
            if len(conversation_data.situation) > 10:
                raise HTTPException(
                    status_code=400,
                    detail="Situation must be 500 characters or less"
                )
            
            self.logger.debug("Conversation data validation passed")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Validation failed: {str(e)}"
            )
    
    def get_user_conversations(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve conversations for a specific user.
        
        Args:
            user_id (str): The ID of the user
            limit (int): Maximum number of conversations to return
            
        Returns:
            List[Dict[str, Any]]: List of user conversations
            
        Raises:
            HTTPException: If retrieval fails
        """
        try:
            if not ObjectId.is_valid(user_id):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid user ID format"
                )
            
            # Use repository to get user conversations
            conversations = self.conversation_repo.get_user_conversations(
                user_id=user_id,
                limit=limit
            )
            
            # Format conversations for response
            formatted_conversations = []
            for conv in conversations:
                conv["id"] = str(conv["_id"])
                conv["user_id"] = str(conv["user_id"])
                del conv["_id"]
                formatted_conversations.append(conv)
            
            self.logger.debug(f"Retrieved {len(formatted_conversations)} conversations for user {user_id}")
            return formatted_conversations
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to retrieve conversations for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve conversations: {str(e)}"
            )
    
    def _format_conversation_response(self, conversation_id: ObjectId) -> Dict[str, Any]:
        """
        Format conversation data for API response.
        
        Args:
            conversation_id (ObjectId): The conversation ID
            
        Returns:
            Dict[str, Any]: Formatted conversation data
        """
        conversation = self.conversation_repo.get_conversation_by_id(str(conversation_id))
        conversation["id"] = str(conversation["_id"])
        conversation["user_id"] = str(conversation["user_id"])
        del conversation["_id"]
        return conversation
    
    def _format_message_response(
        self, 
        message: Message, 
        conversation_id: ObjectId
    ) -> Dict[str, Any]:
        """
        Format message data for API response.
        
        Args:
            message (Message): The message object
            conversation_id (ObjectId): The conversation ID
            
        Returns:
            Dict[str, Any]: Formatted message data
        """
        message_dict = message.to_dict()
        message_dict["id"] = str(message_dict["_id"])
        message_dict["conversation_id"] = str(conversation_id)
        del message_dict["_id"]
        return message_dict 