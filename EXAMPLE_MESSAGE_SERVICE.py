"""
EXAMPLE: Proper MessageService Implementation
This file demonstrates how to implement MessageService following clean architecture principles.

This should be placed at: /workspace/app/services/message_service.py
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException, BackgroundTasks

from app.repositories.message_repository import MessageRepository
from app.repositories.audio_repository import AudioRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.services.conversation_service import ConversationService
from app.services.feedback_service import FeedbackService
from app.services.ai_service import AIService
from app.schemas.message import MessageCreate, MessageResponse
from app.utils.object_id import mongo_doc_to_schema

logger = logging.getLogger(__name__)


class MessageService:
    """
    Service for handling message-related business logic.
    
    This service follows clean architecture principles:
    - Uses repositories for data operations
    - Uses other services for business logic delegation
    - Contains no direct database access
    - Handles all message-related business rules
    """
    
    def __init__(
        self,
        message_repo: Optional[MessageRepository] = None,
        audio_repo: Optional[AudioRepository] = None,
        feedback_repo: Optional[FeedbackRepository] = None,
        conversation_service: Optional[ConversationService] = None,
        feedback_service: Optional[FeedbackService] = None,
        ai_service: Optional[AIService] = None
    ):
        """Initialize MessageService with dependency injection."""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Repositories for data operations
        self.message_repo = message_repo or MessageRepository()
        self.audio_repo = audio_repo or AudioRepository()
        self.feedback_repo = feedback_repo or FeedbackRepository()
        
        # Services for business logic delegation
        self.conversation_service = conversation_service or ConversationService()
        self.feedback_service = feedback_service or FeedbackService()
        self.ai_service = ai_service or AIService()
    
    async def add_message_and_get_response(
        self,
        conversation_id: str,
        audio_id: str,
        user_id: str,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """
        Process user message and generate AI response.
        
        This method orchestrates the entire message processing workflow:
        1. Validates conversation access
        2. Creates user message from audio
        3. Generates AI response
        4. Schedules background feedback processing
        
        Args:
            conversation_id: ID of the conversation
            audio_id: ID of the audio file containing user message
            user_id: ID of the user sending the message
            background_tasks: FastAPI background tasks for async processing
            
        Returns:
            Dict containing user message and AI response
            
        Raises:
            HTTPException: If processing fails
        """
        try:
            # Step 1: Validate conversation access using conversation service
            conversation_context = self.conversation_service.get_conversation_context(conversation_id)
            conversation = conversation_context["conversation"]
            
            # Verify user owns the conversation
            if str(conversation["user_id"]) != user_id:
                raise HTTPException(status_code=403, detail="Access denied to this conversation")
            
            # Step 2: Get audio data using repository
            audio_data = self.audio_repo.find_by_id(audio_id)
            if not audio_data:
                raise HTTPException(status_code=404, detail="Audio data not found")
            
            # Step 3: Create user message using repository
            user_message_doc = self.message_repo.create_message(
                conversation_id=conversation_id,
                sender="user",
                content=audio_data["transcription"],
                audio_path=audio_data["file_path"],
                transcription=audio_data["transcription"]
            )
            
            # Step 4: Schedule feedback processing using feedback service
            background_tasks.add_task(
                self.feedback_service.generate_speech_feedback,
                transcription=audio_data["transcription"],
                user_id=user_id,
                conversation_id=conversation_id,
                audio_id=str(audio_data["_id"]),
                file_path=audio_data["file_path"],
                user_message_id=str(user_message_doc['_id'])
            )
            
            # Step 5: Generate AI response using AI service
            ai_response = await self._generate_ai_response(conversation_context)
            
            # Step 6: Store AI response using repository
            ai_message_doc = self.message_repo.create_message(
                conversation_id=conversation_id,
                sender="ai",
                content=ai_response
            )
            
            # Step 7: Format response using utils
            user_message = mongo_doc_to_schema(user_message_doc, MessageResponse)
            ai_message = mongo_doc_to_schema(ai_message_doc, MessageResponse)
            
            self.logger.info(f"Successfully processed message for conversation {conversation_id}")
            
            return {
                "user_message": user_message,
                "ai_message": ai_message
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process message: {str(e)}"
            )
    
    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a message by its ID.
        
        Args:
            message_id: ID of the message to retrieve
            
        Returns:
            Message data or None if not found
            
        Raises:
            HTTPException: If retrieval fails
        """
        try:
            # Use repository for data operation
            message = self.message_repo.get_message_by_id(message_id)
            if not message:
                return None
                
            self.logger.debug(f"Retrieved message {message_id}")
            return message
            
        except Exception as e:
            self.logger.error(f"Error retrieving message {message_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve message"
            )
    
    def get_message_feedback(self, message_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get feedback for a specific message.
        
        Args:
            message_id: ID of the message
            user_id: ID of the requesting user
            
        Returns:
            Feedback data
            
        Raises:
            HTTPException: If message not found or access denied
        """
        try:
            # Get message using repository
            message = self.message_repo.get_message_by_id(message_id)
            if not message:
                raise HTTPException(status_code=404, detail="Message not found")
            
            # Check if message has feedback
            feedback_id = message.get("feedback_id")
            if not feedback_id:
                return {
                    "user_feedback": "Feedback is still being generated. Please try again in a moment.",
                    "is_ready": False
                }
            
            # Get feedback using repository
            feedback = self.feedback_repo.find_by_id(feedback_id)
            if not feedback:
                return {
                    "user_feedback": "No feedback available for this message.",
                    "is_ready": False
                }
            
            # Format feedback response
            feedback_dict = {
                "id": str(feedback.get("_id", "")),
                "user_feedback": feedback.get("user_feedback", "Feedback content unavailable"),
                "created_at": feedback.get("created_at", datetime.now().isoformat())
            }
            
            self.logger.info(f"Retrieved feedback for message {message_id}")
            return {"user_feedback": feedback_dict, "is_ready": True}
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error getting message feedback: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to get message feedback"
            )
    
    def get_conversation_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all messages for a conversation.
        
        Args:
            conversation_id: ID of the conversation
            user_id: ID of the requesting user
            limit: Maximum number of messages to return
            
        Returns:
            List of messages
            
        Raises:
            HTTPException: If access denied or retrieval fails
        """
        try:
            # Verify conversation access using conversation service
            conversation_context = self.conversation_service.get_conversation_context(conversation_id)
            conversation = conversation_context["conversation"]
            
            if str(conversation["user_id"]) != user_id:
                raise HTTPException(status_code=403, detail="Access denied to this conversation")
            
            # Get messages using repository
            messages = self.message_repo.get_messages_by_conversation(conversation_id, limit)
            
            self.logger.debug(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
            return messages
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error getting conversation messages: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve conversation messages"
            )
    
    async def _generate_ai_response(self, conversation_context: Dict[str, Any]) -> str:
        """
        Generate AI response using AI service.
        
        Args:
            conversation_context: Context from conversation service
            
        Returns:
            AI response text
        """
        try:
            # Build conversation prompt using AI service
            messages = conversation_context["messages"]
            conversation = conversation_context["conversation"]
            
            conversation_history_text = "\n".join([
                f"{msg['sender']}: {msg['content']}" for msg in messages
            ])
            
            prompt = self.ai_service.build_conversation_prompt(
                conversation, 
                conversation_history_text
            )
            
            # Generate response using AI service
            ai_response = self.ai_service.generate_ai_response(prompt)
            
            self.logger.debug("Generated AI response")
            return ai_response
            
        except Exception as e:
            self.logger.error(f"Error generating AI response: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate AI response"
            )


# Example of how to use this service in dependency injection
def get_message_service() -> MessageService:
    """Dependency injection factory for MessageService."""
    return MessageService()


"""
USAGE IN ROUTES:

# OLD WAY (❌ WRONG):
from app.repositories.message_repository import MessageRepository
from app.repositories.audio_repository import AudioRepository
message_repo = MessageRepository()
audio_repo = AudioRepository()
# ... complex business logic in route

# NEW WAY (✅ CORRECT):
from app.services.message_service import MessageService
from app.utils.dependencies import get_message_service

@router.post("/conversations/{conversation_id}/message")
async def add_message_and_get_response(
    conversation_id: str,
    audio_id: str,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    message_service: MessageService = Depends(get_message_service)
):
    user_id = str(current_user["_id"])
    return await message_service.add_message_and_get_response(
        conversation_id=conversation_id,
        audio_id=audio_id,
        user_id=user_id,
        background_tasks=background_tasks
    )
"""