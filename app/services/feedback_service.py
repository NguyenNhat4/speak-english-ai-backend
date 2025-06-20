"""
Feedback Service for handling feedback-related business logic.

This service manages feedback generation, processing, and analysis
for the SpeakAI application using clean architecture principles.
It orchestrates the feedback workflow while delegating AI operations to AIService.
"""

import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from bson import ObjectId
from pathlib import Path
import shutil
from fastapi import HTTPException, UploadFile, Depends
from dataclasses import dataclass

from app.models.feedback import Feedback
from app.models.results.feedback_result import FeedbackResult
from app.services.ai_service import AIService, ConversationContext
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.utils.file_utils import (
    validate_audio_file,
    save_uploaded_file,
    cleanup_temp_file,
    sanitize_filename,
    UPLOAD_DIR
)
from app.utils.object_id import str_to_object_id, mongo_doc_to_dict
MAX_CONTEXT_MESSAGES = 10


@dataclass
class FeedbackRequest:
    """Data class for feedback generation requests."""
    transcription: str
    user_id: str
    conversation_id: str
    audio_id: str
    file_path: str
    user_message_id: str


class FeedbackServiceError(Exception):
    """Custom exception for feedback service errors."""
    pass


class FeedbackService:
    """
    Service class for handling feedback business logic.
    
    This service provides functionality to:
    1. Orchestrate feedback generation workflow
    2. Process speech feedback in background tasks
    3. Store feedback in the database
    4. Handle audio file uploads and processing
    
    Follows clean architecture principles with proper separation of concerns.
    AI-related operations are delegated to AIService.
    """
    
    def __init__(
        self,
        ai_service: Optional[AIService] = None,
        conversation_repo: Optional[ConversationRepository] = None,
        message_repo: Optional[MessageRepository] = None,
        feedback_repo: Optional[FeedbackRepository] = None,
    ):
        """Initialize the feedback service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ai_service = ai_service or AIService()
        self.conversation_repo = conversation_repo or ConversationRepository()
        self.message_repo = message_repo or MessageRepository()
        self.feedback_repo = feedback_repo or FeedbackRepository()
        self._validate_dependencies()
    
    def _validate_dependencies(self) -> None:
        """Validate that required dependencies are available."""
        if not all([self.ai_service, self.conversation_repo, self.message_repo, self.feedback_repo]):
            raise FeedbackServiceError("One or more service dependencies are not available")
        
        # Ensure upload directory exists
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create upload directory: {e}")
            raise FeedbackServiceError("Upload directory not accessible")
    
    async def generate_speech_feedback(
        self,
        transcription: str,
        user_id: str,
        conversation_id: str,
        audio_id: str,
        file_path: str,
        user_message_id: str
    ) -> Dict[str, Any]:
        """
        Generate feedback for speech transcription.
        
        Args:
            transcription: The transcribed text
            user_id: The ID of the user
            conversation_id: The ID of the conversation
            audio_id: The ID of the audio file
            file_path: Path to the audio file
            user_message_id: The ID of the user message
            
        Returns:
            Dict containing feedback generation results
            
        Raises:
            HTTPException: If feedback generation fails
        """
        try:
            request = FeedbackRequest(
                transcription=transcription,
                user_id=user_id,
                conversation_id=conversation_id,
                audio_id=audio_id,
                file_path=file_path,
                user_message_id=user_message_id
            )
            
            self._validate_feedback_request(request)
            
            # Fetch conversation context
            context = await self._fetch_conversation_context(conversation_id)
            
            # Generate feedback using AI service
            feedback_result = await self._generate_feedback_with_ai(request.transcription, context)
            
            # Store feedback in database
            feedback_id = await self._store_feedback_safe(
                user_id=request.user_id,
                feedback_data=feedback_result,
                user_message_id=request.user_message_id,
                transcription=request.transcription
            )
            
            # Link feedback to message
            await self._link_feedback_to_message(request.user_message_id, feedback_id)
            
            self.logger.info(f"Successfully generated feedback for user {user_id}")
            
            return self._build_success_response(request, feedback_id)
            
        except FeedbackServiceError as e:
            self.logger.error(f"Feedback service error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            self.logger.error(f"Unexpected error in feedback generation: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred during feedback generation"
            )

    def _validate_feedback_request(self, request: FeedbackRequest) -> None:
        """Validate feedback request parameters."""
        if not request.transcription or not request.transcription.strip():
            raise FeedbackServiceError("Transcription cannot be empty")
        
        if len(request.transcription) > 5000:  # Reasonable limit
            raise FeedbackServiceError("Transcription too long")
        
        try:
            ObjectId(request.user_id)
            ObjectId(request.conversation_id)
            ObjectId(request.audio_id)
            ObjectId(request.user_message_id)
        except Exception:
            raise FeedbackServiceError("Invalid ID format provided")
    
    async def _fetch_conversation_context(self, conversation_id: str) -> ConversationContext:
        """Fetch and build conversation context."""
        try:
            conversation = self.conversation_repo.get_conversation_by_id(conversation_id)
            if not conversation:
                self.logger.warning(f"Conversation not found: {conversation_id}")
                return ConversationContext()
            
            # Fetch recent messages for context
            messages = self.message_repo.get_messages_by_conversation(
                conversation_id, limit=MAX_CONTEXT_MESSAGES
            )
            
            # Format previous exchanges
            previous_exchanges = []
            for msg in messages:
                sender = "User" if msg.get("sender") == "user" else "AI"
                content = msg.get("content", "").strip()
                if content:
                    previous_exchanges.append(f"{sender}: {content}")
            
            return ConversationContext(
                user_role=conversation.get("user_role", "Student"),
                ai_role=conversation.get("ai_role", "Teacher"),
                situation=conversation.get("situation", "General conversation"),
                previous_exchanges="\n".join(previous_exchanges)
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching conversation context: {e}")
            return ConversationContext()  # Return default context on error
    
    async def _generate_feedback_with_ai(
        self, 
        transcription: str, 
        context: ConversationContext
    ) -> FeedbackResult:
        """Generate feedback using AI service with fallback handling."""
        try:
            # Use AI service to generate feedback
            return self.ai_service.generate_feedback(transcription, context)
        except Exception as e:
            self.logger.error(f"AI feedback generation failed: {e}")
            # Use AI service fallback
            return self.ai_service.generate_fallback_feedback(transcription)
    
    async def _store_feedback_safe(
        self,
        user_id: str,
        feedback_data: FeedbackResult,
        user_message_id: str,
        transcription: str
    ) -> str:
        """Store feedback with proper error handling."""
        try:
            return await self._store_feedback(user_id, feedback_data, user_message_id, transcription)
        except Exception as e:
            self.logger.error(f"Error storing feedback: {e}")
            raise FeedbackServiceError(f"Failed to store feedback: {e}")
    
    async def _link_feedback_to_message(self, user_message_id: str, feedback_id: str) -> None:
        """Link feedback to the user message."""
        try:
            result = self.message_repo.update_message_feedback(user_message_id, feedback_id)
            
            if not result:
                self.logger.warning(f"Failed to link feedback {feedback_id} to message {user_message_id}")
                
        except Exception as e:
            self.logger.error(f"Error linking feedback to message: {e}")
            # Don't raise here as feedback was already generated successfully
    
    def _build_success_response(self, request: FeedbackRequest, feedback_id: str) -> Dict[str, Any]:
        """Build success response for feedback generation."""
        sanitized_filename = sanitize_filename(request.file_path)
        return {
            "status": "success",
            "message": "Feedback generated successfully.",
            "feedback_id": feedback_id,
            "user_id": request.user_id,
            "conversation_id": request.conversation_id,
            "audio_id": request.audio_id,
            "user_message_id": request.user_message_id,
            "timestamp": datetime.utcnow().isoformat(),
            "file_path": f"/audio/{sanitized_filename}"
        }

    async def save_audio_file(self, file: UploadFile, user_id: str) -> str:
        """
        Saves an uploaded audio file and returns its path.
        This method is now part of the feedback generation flow.
        """
        self._validate_audio_file(file)
        file_path = await self._save_file_to_disk(file, user_id)
        return str(file_path)

    def _validate_audio_file(self, file: UploadFile) -> None:
        """Validate audio file properties."""
        validate_audio_file(file)

    async def _save_file_to_disk(self, file: UploadFile, user_id: str) -> Path:
        """Save uploaded file to disk."""
        return await save_uploaded_file(file, user_id)

    async def _store_feedback(
        self,
        user_id: str,
        feedback_data: Union[FeedbackResult, Dict[str, Any]],
        user_message_id: Optional[str] = None,
        transcription: Optional[str] = None
    ) -> str:
        """
        Stores feedback data in the database.
        
        This method now directly uses the FeedbackRepository.
        """
        if isinstance(feedback_data, FeedbackResult):
            feedback_dict = feedback_data.dict()
        else:
            feedback_dict = feedback_data

        new_feedback = {
            "user_id": str_to_object_id(user_id),
            "user_message_id": str_to_object_id(user_message_id) if user_message_id else None,
            "transcription": transcription,
            "created_at": datetime.utcnow(),
            **feedback_dict
        }
        
        feedback_id = self.feedback_repo.create(new_feedback)
        
        if user_message_id:
            self._update_conversation_feedback_list(user_message_id, feedback_id)
            
        return feedback_id

    def _validate_object_ids(self, ids: List[str]) -> None:
        """Validate a list of string ObjectIDs."""
        for item_id in ids:
            if not ObjectId.is_valid(item_id):
                raise FeedbackServiceError(f"Invalid ObjectId: {item_id}")

    def _update_conversation_feedback_list(self, message_id: str, feedback_id: str) -> None:
        """
        Update the conversation's feedback list with the new feedback ID.
        """
        try:
            self.message_repo.update_conversation_feedback_list(message_id, feedback_id)
        except Exception as e:
            self.logger.error(f"Error updating conversation feedback list: {e}")
            # Non-critical error, so we don't re-raise
    