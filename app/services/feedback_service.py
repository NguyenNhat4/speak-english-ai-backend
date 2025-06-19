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
from fastapi import HTTPException, UploadFile
from dataclasses import dataclass

from app.config.database import db
from app.models.feedback import Feedback
from app.models.results.feedback_result import FeedbackResult
from app.services.ai_service import AIService, ConversationContext

logger = logging.getLogger(__name__)

# Constants
UPLOAD_DIR = Path("app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
VALID_AUDIO_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac']
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
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
    
    def __init__(self):
        """Initialize the feedback service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ai_service = AIService()
        self._validate_dependencies()
    
    def _validate_dependencies(self) -> None:
        """Validate that required dependencies are available."""
        if db is None:
            raise FeedbackServiceError("Database connection not available")
        
        if not self.ai_service:
            raise FeedbackServiceError("AI service not available")
        
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
            conversation = db.conversations.find_one({"_id": ObjectId(conversation_id)})
            if not conversation:
                self.logger.warning(f"Conversation not found: {conversation_id}")
                return ConversationContext()
            
            # Fetch recent messages for context
            messages = list(
                db.messages.find({"conversation_id": ObjectId(conversation_id)})
                .sort("timestamp", 1)
                .limit(MAX_CONTEXT_MESSAGES)
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
            return self._store_feedback(user_id, feedback_data, user_message_id, transcription)
        except Exception as e:
            self.logger.error(f"Error storing feedback: {e}")
            raise FeedbackServiceError(f"Failed to store feedback: {e}")
    
    async def _link_feedback_to_message(self, user_message_id: str, feedback_id: str) -> None:
        """Link feedback to the user message."""
        try:
            result = db.messages.update_one(
                {"_id": ObjectId(user_message_id)},
                {"$set": {"feedback_id": feedback_id}}
            )
            
            if result.modified_count == 0:
                self.logger.warning(f"Failed to link feedback {feedback_id} to message {user_message_id}")
                
        except Exception as e:
            self.logger.error(f"Error linking feedback to message: {e}")
            # Don't raise here as feedback was already generated successfully
    
    def _build_success_response(self, request: FeedbackRequest, feedback_id: str) -> Dict[str, Any]:
        """Build success response for feedback generation."""
        return {
            "status": "success",
            "feedback_id": feedback_id,
            "user_id": request.user_id,
            "conversation_id": request.conversation_id,
            "audio_id": request.audio_id,
            "user_message_id": request.user_message_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    

    
    async def save_audio_file(self, file: UploadFile, user_id: str) -> str:
        """
        Save an uploaded audio file to the server.
        
        Args:
            file: The audio file to save
            user_id: ID of the user
            
        Returns:
            Path to the saved file on disk
            
        Raises:
            HTTPException: If file save fails
        """
        try:
            self._validate_audio_file(file)
            self._validate_object_ids([user_id])
            
            file_path = await self._save_file_to_disk(file, user_id)
            
            self.logger.info(f"Successfully saved audio file for user {user_id}: {file_path}")
            return str(file_path)
            
        except FeedbackServiceError as e:
            self.logger.error(f"Audio file validation error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            self.logger.error(f"Failed to save audio file: {e}")
            raise HTTPException(
                status_code=500,
                detail="Audio file save failed"
            )
    
    def _validate_audio_file(self, file: UploadFile) -> None:
        """Validate audio file before saving."""
        if not file.filename:
            raise FeedbackServiceError("Filename is required")
        
        # Check file extension
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in VALID_AUDIO_EXTENSIONS:
            raise FeedbackServiceError(
                f"Invalid file type. Supported formats: {', '.join(VALID_AUDIO_EXTENSIONS)}"
            )
        
        # Check file size (if available)
        if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
            raise FeedbackServiceError(f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    async def _save_file_to_disk(self, file: UploadFile, user_id: str) -> Path:
        """Save file to disk with proper error handling."""
        try:
            # Create user directory
            user_dir = UPLOAD_DIR / str(user_id)
            user_dir.mkdir(exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
            filename = file.filename or "audio_file"
            safe_filename = self._sanitize_filename(f"{timestamp}_{filename}")
            file_path = user_dir / safe_filename
            
            # Save the file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            return file_path
            
        except Exception as e:
            raise FeedbackServiceError(f"Failed to save file to disk: {e}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage."""
        # Replace spaces and unsafe characters
        safe_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        sanitized = "".join(c if c in safe_chars else "_" for c in filename)
        # Replace multiple underscores/spaces with single underscore
        while "__" in sanitized or "  " in sanitized:
            sanitized = sanitized.replace("__", "_").replace("  ", " ")
        return sanitized.replace(" ", "_").strip("_")

    def _store_feedback(
        self, 
        user_id: str, 
        feedback_data: Union[FeedbackResult, Dict[str, Any]], 
        user_message_id: Optional[str] = None, 
        transcription: Optional[str] = None
    ) -> str:
        """
        Store feedback in the database.
        
        Args:
            user_id: ID of the user who received the feedback
            feedback_data: Feedback data to store
            user_message_id: Optional ID of the associated message
            transcription: Optional transcription text
            
        Returns:
            ID of the stored feedback
        """
        try:
            # Validate and convert IDs
            user_object_id = ObjectId(user_id)
            target_id = ObjectId(user_message_id) if user_message_id else ObjectId()
            
            # Extract feedback content
            if isinstance(feedback_data, FeedbackResult):
                user_feedback = feedback_data.user_feedback
            else:
                user_feedback = feedback_data.get("user_feedback", "")
            
            if not user_feedback:
                raise FeedbackServiceError("Feedback content cannot be empty")
            
            # Create feedback model
            feedback = Feedback(
                user_id=user_object_id,
                target_id=target_id,
                target_type="message" if user_message_id else "conversation",
                transcription=transcription or "",
                user_feedback=user_feedback,
            )
            
            # Insert feedback into database
            result = db.feedback.insert_one(feedback.to_dict())
            
            if not result.inserted_id:
                raise FeedbackServiceError("Failed to insert feedback into database")
            
            # Update conversation record if applicable
            if user_message_id:
                self._update_conversation_feedback_list(user_message_id, str(result.inserted_id))
            
            return str(result.inserted_id)
                
        except Exception as e:
            self.logger.error(f"Error storing feedback: {e}")
            raise FeedbackServiceError(f"Failed to store feedback: {e}")
    
    def _update_conversation_feedback_list(self, message_id: str, feedback_id: str) -> None:
        """Update conversation with feedback ID."""
        try:
            db.conversations.update_one(
                {"_id": ObjectId(message_id)},
                {"$push": {"feedback_ids": feedback_id}}
            )
        except Exception as e:
            self.logger.warning(f"Failed to update conversation feedback list: {e}")
            # Don't raise as this is not critical
    
    def _validate_object_ids(self, ids: List[str]) -> None:
        """Validate that all provided strings are valid ObjectId format."""
        for id_str in ids:
            if not id_str:
                raise FeedbackServiceError("ID cannot be empty")
            try:
                ObjectId(id_str)
            except Exception:
                raise FeedbackServiceError(f"Invalid ObjectId format: {id_str}")
    