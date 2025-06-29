"""
Conversation Service for handling conversation-related business logic.

This service manages conversation creation, retrieval, and validation
for the SpeakAI application.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException, Depends

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationCreate, ConversationResponse, ConversationUpdate
from app.schemas.message import MessageResponse
from app.utils.ai_utils import refine_conversation_context

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Service class for handling conversation business logic.
    
    This service encapsulates all conversation-related operations including
    creation, retrieval, validation, and management.
    """
    
    def __init__(
        self, 
        conversation_repo: Optional[ConversationRepository] = None, 
        message_repo: Optional[MessageRepository] = None
    ):
        """
        Initialize the conversation service with repository dependencies.
        
        Args:
            conversation_repo: ConversationRepository instance
            message_repo: MessageRepository instance
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.conversation_repo = conversation_repo or ConversationRepository()
        self.message_repo = message_repo or MessageRepository()
    
    def create_new_conversation(self, user_id: str, convo_data: ConversationCreate) -> Dict[str, Any]:
        """
        Validates, refines context, and creates a new conversation with an initial message.
        """
        self.validate_conversation_data(convo_data)
        
        refined_context = refine_conversation_context(
            user_role=convo_data.user_role,
            ai_role=convo_data.ai_role,
            situation=convo_data.situation
        )
        
        return self.create_conversation(
            user_id=user_id,
            refined_context=refined_context
        )

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
            if not conversation_data:
                raise HTTPException(status_code=404, detail="Failed to format conversation response")

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
            # The repository now handles ObjectId validation
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
            # The repository now handles ObjectId validation
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
    
    def _format_conversation_response(self, conversation_id: ObjectId) -> Optional[Dict[str, Any]]:
        """
        Format a conversation for API response.
        
        Args:
            conversation_id: The ID of the conversation
            
        Returns:
            Formatted conversation data or None
        """
        conversation = self.conversation_repo.get_conversation_by_id(str(conversation_id))
        if not conversation:
            return None
            
        return {
            "id": str(conversation["_id"]),
            "user_id": str(conversation["user_id"]),
            "user_role": conversation["user_role"],
            "ai_role": conversation["ai_role"],
            "situation": conversation["situation"],
            "started_at": conversation["started_at"].isoformat(),
            "ended_at": conversation["ended_at"].isoformat() if conversation.get("ended_at") else None,
            "voice_type": conversation.get("voice_type")
        }
    
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
        return {
            "id": str(message._id),
            "conversation_id": str(conversation_id),
            "sender": message.sender,
            "content": message.content,
            "timestamp": message.timestamp.isoformat()
        }

    def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single conversation by its ID.
        """
        conversation = self.conversation_repo.get_conversation_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation

    def update_conversation(self, conversation_id: str, update_data: ConversationUpdate) -> Optional[Dict[str, Any]]:
        """
        Update conversation metadata.
        """
        update_dict = update_data.dict(exclude_unset=True)
        updated_conversation = self.conversation_repo.update(conversation_id, update_dict)
        if not updated_conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return updated_conversation

    def delete_conversation(self, conversation_id: str):
        """
        Delete a conversation.
        """
        deleted = self.conversation_repo.delete(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"message": "Conversation deleted successfully"} 