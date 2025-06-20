from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from bson import ObjectId
from typing import List, Optional
import logging
import asyncio
from datetime import datetime

from app.schemas.message import MessageCreate, MessageResponse
from app.models.message import Message
from app.utils.auth import get_current_user
from app.services.conversation_service import ConversationService
from app.services.feedback_service import FeedbackService
from app.services.ai_service import AIService
from app.repositories.message_repository import MessageRepository
from app.repositories.audio_repository import AudioRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.utils.dependencies import (
    get_conversation_service,
    get_feedback_service,
    get_ai_service,
    get_message_repository,
    get_audio_repository,
    get_feedback_repository
)
from app.utils.object_id import mongo_doc_to_schema

# Set up logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# ====================
# MESSAGE ENDPOINTS
# ====================

@router.post("/conversations/{conversation_id}/message", response_model=dict)
async def add_message_and_get_response (
    conversation_id: str,  
    audio_id: str ,  
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    conversation_service: ConversationService = Depends(get_conversation_service),
    feedback_service: FeedbackService = Depends(get_feedback_service),
    ai_service: AIService = Depends(get_ai_service),
    message_repository: MessageRepository = Depends(get_message_repository),
    audio_repository: AudioRepository = Depends(get_audio_repository)
):
    """
    Process speech audio and return an AI response.
    
    This endpoint:
    1. Retrieves the transcribed audio using the provided audio_id
    2. Adds the user's message to the conversation
    3. Generates an AI response based on conversation context
    4. Handles feedback generation in the background
    """   
    try:
        user_id = str(current_user["_id"])
        
        # Get conversation context using conversation service
        conversation_context = conversation_service.get_conversation_context(conversation_id)
        conversation = conversation_context["conversation"]
        
        # Verify user owns the conversation
        if str(conversation["user_id"]) != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this conversation")
        
        # Get audio data using repository
        audio_data = audio_repository.find_by_id(audio_id)
        if not audio_data:
            raise HTTPException(status_code=404, detail="Audio data not found")
        
        # Create user message
        user_message_doc = message_repository.create_message(
            conversation_id=conversation_id,
            sender="user",
            content=audio_data["transcription"],
            audio_path=audio_data["file_path"],
            transcription=audio_data["transcription"]
        )
        
        # Schedule feedback processing in background using service
        background_tasks.add_task(
            feedback_service.generate_speech_feedback,
            transcription=audio_data["transcription"],
            user_id=user_id,
            conversation_id=conversation_id,
            audio_id=str(audio_data["_id"]),
            file_path=audio_data["file_path"],
            user_message_id=str(user_message_doc['_id'])
        )
        
        # Get conversation history from the context
        messages = conversation_context["messages"]
        
        # Build conversation prompt using AI service
        conversation_history_text = "\n".join([f"{msg['sender']}: {msg['content']}" for msg in messages])
        prompt = ai_service.build_conversation_prompt(conversation, conversation_history_text)

        # Generate AI response using AI service
        ai_text = ai_service.generate_ai_response(prompt)
        
        # Store AI response
        ai_message_doc = message_repository.create_message(
            conversation_id=conversation_id,
            sender="ai",
            content=ai_text
        )
        
        # Convert documents to response format using utility
        user_message = mongo_doc_to_schema(user_message_doc, MessageResponse)
        ai_message = mongo_doc_to_schema(ai_message_doc, MessageResponse)
        
        return {
            "user_message": user_message,
            "ai_message": ai_message
        }
            
    except Exception as e:
        logger.error(f"Error in /conversations/{conversation_id}/message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed in /conversations/{conversation_id}/message: {str(e)}"
        )

@router.get("/messages/{message_id}/feedback", response_model=dict)
async def get_message_feedback(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    message_repository: MessageRepository = Depends(get_message_repository),
    feedback_repository: FeedbackRepository = Depends(get_feedback_repository)
):
    """
    Get user-friendly feedback for a specific message.
    
    This endpoint retrieves the stored feedback for a message when the user
    clicks the feedback button in the UI.
    """
    try:
        # Find the message
        message = message_repository.get_message_by_id(message_id)
        if not message:
            logger.warning(f"Message not found: {message_id}")
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Check if message has associated feedback
        feedback_id = message.get("feedback_id")
        if not feedback_id:
            logger.info(f"No feedback_id found for message: {message_id}, feedback may still be processing")
            return {"user_feedback": "Feedback is still being generated. Please try again in a moment.", "is_ready": False}
        
        logger.info(f"Found feedback_id: {feedback_id}, retrieving feedback document")
        
        # Get the feedback document
        feedback = feedback_repository.find_by_id(feedback_id)
        if not feedback:
            logger.warning(f"No feedback found with ID: {feedback_id}")
            return {"user_feedback": "No feedback available for this message.", "is_ready": False}
            
        # Create a safe dictionary from the feedback document
        feedback_dict = {
            "id": str(feedback.get("_id", "")),
            "user_feedback": feedback.get("user_feedback", "Feedback content unavailable"),
            "created_at": feedback.get("created_at", datetime.now().isoformat())
        }
        
        logger.info(f"Feedback document: {feedback_dict}")
        return {"user_feedback": feedback_dict, "is_ready": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting message feedback for message {message_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message feedback"
        )

# GET /messages/{message_id} - Get message details (to be implemented)
# This endpoint will retrieve a specific message with its content and metadata

# PUT /messages/{message_id} - Update message (to be implemented)
# This endpoint will allow updating message content or metadata

# DELETE /messages/{message_id} - Delete message (to be implemented)
# This endpoint will handle message deletion

# GET /conversations/{conversation_id}/messages - List conversation messages (to be implemented)
# This endpoint will retrieve all messages for a specific conversation 