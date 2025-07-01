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
from app.schemas.conversation import ConversationCreate, ConversationResponse, ConversationUpdate, ConversationContext
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
            
            # Prepare response data
            conversation_obj = self.get_conversation_by_id(conversation_id)
            if not conversation_obj:
                raise HTTPException(status_code=404, detail="Failed to format conversation response")

            # Create initial AI message using repository
            initial_message = self.message_repo.create_message(
                conversation_id=conversation_id,
                sender="ai",
                content=refined_context["response"]
            )

            message_obj = MessageResponse.model_validate(initial_message)
            
            self.logger.info(f"Successfully created conversation {conversation_id} for user {user_id}")
            
            return {
                "conversation": conversation_obj,
                "initial_message": message_obj
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create conversation for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create conversation: {str(e)}"
            )
    
    def get_conversation_context(self, conversation_id: str) -> ConversationContext:
        """
        Retrieve conversation context and message history.
        
        Args:
            conversation_id (str): The ID of the conversation to retrieve
            
        Returns:
            ConversationContext: Conversation data and message history
            
        Raises:
            HTTPException: If conversation not found or retrieval fails
        """
        try:
            # The repository now handles ObjectId validation
            conversation_data = self.conversation_repo.get_conversation_by_id(conversation_id)
            if not conversation_data:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found"
                )
            
            # Fetch messages for the conversation using repository
            messages_data = self.message_repo.get_messages_by_conversation(conversation_id)
            
            # Format message history for AI context
            history = [
                {
                    "role": "user" if msg["sender"] == "user" else "model",
                    "parts": [msg["content"]]
                }
                for msg in messages_data
            ]
            
            self.logger.debug(f"Retrieved conversation context for {conversation_id} with {len(messages_data)} messages")
            
            return ConversationContext(
                conversation=ConversationResponse.model_validate(conversation_data),
                messages=[MessageResponse.model_validate(msg) for msg in messages_data],
                history=history
            )
            
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
    
    def get_user_conversations(self, user_id: str, limit: int = 50) -> List[ConversationResponse]:
        """
        Retrieve conversations for a specific user.
        
        Args:
            user_id (str): The ID of the user
            limit (int): Maximum number of conversations to return
            
        Returns:
            List[ConversationResponse]: List of user conversations
            
        Raises:
            HTTPException: If retrieval fails
        """
        try:
            # The repository now handles ObjectId validation
            conversations = self.conversation_repo.get_user_conversations(
                user_id=user_id,
                limit=limit
            )
            
            return [ConversationResponse.model_validate(conv) for conv in conversations]
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to retrieve conversations for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve conversations: {str(e)}"
            )
    
    def get_conversation_by_id(self, conversation_id: str) -> ConversationResponse:
        """
        Retrieve a single conversation by its ID.
        """
        conversation = self.conversation_repo.get_conversation_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationResponse.model_validate(conversation)

    def update_conversation(self, conversation_id: str, update_data: ConversationUpdate) -> Optional[ConversationResponse]:
        """
        Update conversation metadata.
        """
        update_dict = update_data.model_dump(exclude_unset=True)
        updated_conversation = self.conversation_repo.update(conversation_id, update_dict)
        if not updated_conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationResponse.model_validate(updated_conversation)

    def delete_conversation(self, conversation_id: str):
        """
        Delete a conversation.
        """
        deleted = self.conversation_repo.delete(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"message": "Conversation deleted successfully"} 