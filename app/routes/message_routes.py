from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from bson import ObjectId
from typing import List, Optional
import logging
import asyncio
from datetime import datetime

from app.config.database import db
from app.schemas.message import MessageCreate, MessageResponse
from app.models.message import Message
from app.utils.auth import get_current_user
from app.services.conversation_service import ConversationService
from app.services.feedback_service import FeedbackService
from app.services.ai_service import AIService
from app.repositories.message_repository import MessageRepository
from app.repositories.audio_repository import AudioRepository
from app.repositories.feedback_repository import FeedbackRepository

# Set up logger
logger = logging.getLogger(__name__)

# Initialize services
conversation_service = ConversationService()
feedback_service = FeedbackService()
ai_service = AIService()

# Initialize repositories
message_repository = MessageRepository()
audio_repository = AudioRepository()
feedback_repository = FeedbackRepository()

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
    background_tasks: BackgroundTasks = BackgroundTasks()
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
                
                # Step 1: Fetch the audio and conversation data using services
                async def get_audio():
                    return db.audio.find_one({"_id": ObjectId(audio_id)})
                    
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
                
                # Return AI response in MessageResponse format
                # Convert documents to response format
                ai_message_dict = {
                    "id": str(ai_message_doc["_id"]),
                    "conversation_id": str(ai_message_doc["conversation_id"]),
                    "sender": ai_message_doc["sender"],
                    "content": ai_message_doc["content"],
                    "audio_path": ai_message_doc.get("audio_path"),
                    "transcription": ai_message_doc.get("transcription"),
                    "feedback_id": ai_message_doc.get("feedback_id"),
                    "timestamp": ai_message_doc["timestamp"]
                }
                
                user_message_dict = {
                    "id": str(user_message_doc["_id"]),
                    "conversation_id": str(user_message_doc["conversation_id"]),
                    "sender": user_message_doc["sender"],
                    "content": user_message_doc["content"],
                    "audio_path": user_message_doc.get("audio_path"),
                    "transcription": user_message_doc.get("transcription"),
                    "feedback_id": user_message_doc.get("feedback_id"),
                    "timestamp": user_message_doc["timestamp"]
                }
                
                return {
                    "user_message": MessageResponse(**user_message_dict),
                    "ai_message": MessageResponse(**ai_message_dict)
                }
            
       
    except Exception as e:
        logger.error(f"Error /conversations/{conversation_id}/speechtomessage: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed at /conversations/{conversation_id}/speechtomessage: {str(e)}"
        )


@router.get("/messages/{message_id}/feedback",response_model=dict)
async def get_message_feedback(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get user-friendly feedback for a specific message.
    
    This endpoint retrieves the stored feedback for a message when the user
    clicks the feedback button in the UI.
    """
    try:
        user_id = str(current_user["_id"])
        # Find the message
        message = message_repository.get_message_by_id(message_id)
        if not message:
            logger.warning(f"Message not found: {message_id}")
            raise HTTPException(status_code=404, detail="Message not found")
        
        
        # Check if message has associated feedback
        feedback_id = message.get("feedback_id")
        if not feedback_id:
            logger.info(f"No feedback_id found for message: {message_id}, feedback may still be processing")
            # Feedback might still be processing
            return {"user_feedback": "Feedback is still being generated. Please try again in a moment.", "is_ready": False}
        
        logger.info(f"Found feedback_id: {feedback_id}, retrieving feedback document")
        
        # Get the feedback document
        try:
            feedback = feedback_repository.find_by_id(feedback_id)
            # Log the structure of the feedback document to understand its contents
            logger.info(f"Feedback document structure: {type(feedback).__name__}, keys: {list(feedback.keys()) if feedback else 'None'}")
        except Exception as e:
            logger.error(f"Error retrieving feedback document: {str(e)}", exc_info=True)
            return {"user_feedback": "Error retrieving feedback. Please try again later.", "is_ready": False}
            
        if not feedback:
            logger.warning(f"No feedback found with ID: {feedback_id}")
            return {"user_feedback": "No feedback available for this message.", "is_ready": False}
            
        # Handle feedback document safely
        try:
            # Create a safe copy with only the fields we need
            
            feedback_dict = {
                "id": str(feedback.get("_id", "")),
                "user_feedback": feedback.get("user_feedback", "Feedback content unavailable"),
                "created_at": feedback.get("created_at", datetime.now().isoformat())
            }
            
            # Add detailed feedback if available
            logger.info(f"Feedback document: {feedback_dict}")
            return {"user_feedback": feedback_dict, "is_ready": True}
        except Exception as e:
            logger.error(f"Error processing feedback document: {str(e)}", exc_info=True)
            return {"user_feedback": "Error processing feedback data. Please try again later.", "is_ready": False}
        
    except Exception as e:
        logger.error(f"Error getting message feedback: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get message feedback: {str(e)}"
        )


# GET /messages/{message_id} - Get message details (to be implemented)
# This endpoint will retrieve a specific message with its content and metadata

# PUT /messages/{message_id} - Update message (to be implemented)
# This endpoint will allow updating message content or metadata

# DELETE /messages/{message_id} - Delete message (to be implemented)
# This endpoint will handle message deletion

# GET /conversations/{conversation_id}/messages - List conversation messages (to be implemented)
# This endpoint will retrieve all messages for a specific conversation 