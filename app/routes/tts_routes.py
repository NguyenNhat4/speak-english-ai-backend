from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from bson import ObjectId
from typing import List, Optional
import logging
import time
from datetime import datetime

from app.config.database import db
from app.utils.auth import get_current_user
from app.utils.tts_client_service import get_speech_from_tts_service
from app.services.tts_service import TTSService
from app.services.conversation_service import ConversationService

# Set up logger
logger = logging.getLogger(__name__)

# Initialize services
tts_service = TTSService()
conversation_service = ConversationService()

# Create router instance
router = APIRouter()

# =============================
# TEXT-TO-SPEECH ENDPOINTS
# =============================

@router.get(
    "/messages/{message_id}/speech",
    summary="Get AI message audio stream",
    description="Retrieves an AI message's text, converts it to speech via an external TTS service, and streams the audio."
)
async def get_ai_message_as_speech_stream( 
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        start = time.time()
        
        logger.info(f"Getting AI message audio stream for message_id: {message_id}")
        
        # Get message data
        message_object_id = ObjectId(message_id)
        message = db.messages.find_one({"_id": message_object_id})
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Validate message is from AI
        if message.get("sender") != "ai":
            raise HTTPException(status_code=400, detail="Speech can only be generated for AI messages")

        ai_text = message.get("content")
        if not ai_text:
            raise HTTPException(status_code=400, detail="AI Message has no text content to synthesize")

        # Get conversation context to retrieve voice type
        conversation_id = str(message["conversation_id"])
        conversation_context = conversation_service.get_conversation_context(conversation_id)
        conversation_voice_type = conversation_context["conversation"]["voice_type"]
        
        end = time.time()
        logger.info(f"Time taken to fetch message and conversation: {end - start} seconds")

        default_lang_code = "en-US"     # Example: set to your primary language
        default_model_name = "kokoro"   # From your TTS API example
        default_response_format = "mp3"
        default_speed = 1.3

        return await get_speech_from_tts_service(
            text_to_speak=ai_text,
            voice_name=conversation_voice_type,
            model_name=default_model_name,
            response_format=default_response_format,
            speed=default_speed,
            lang_code=default_lang_code
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate speech: An internal error occurred.")


@router.get(
    "/messages/demospeech",
    summary="Get AI message audio stream",
    description="Retrieves an AI message's text, converts it to speech via an external TTS service, and streams the audio."
)
async def get_ai_message_as_speech_stream_demo( 
    message: str = "Hello, how are you?"
):
    try:
        conversation_voice_type = "hm_omega"
        default_lang_code = "en-US"     # Example: set to your primary language
        default_model_name = "kokoro"   # From your TTS API example
        default_response_format = "mp3"
        default_speed = 1.3

        # 4. Call the TTS Service via your client function
        #    This function is expected to return a StreamingResponse
        start = time.time()
        stream_response = await get_speech_from_tts_service(
            text_to_speak=message,
            voice_name=conversation_voice_type,
            model_name=default_model_name,
            response_format=default_response_format,
            speed=default_speed,
            lang_code=default_lang_code
        )
        end = time.time()
        
        # Add timing information as a header instead of trying to return it with the stream
        stream_response.headers["X-Processing-Time"] = str(end - start)
        
        return stream_response
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate speech: An internal error occurred.")


@router.get(
    "/messages/{message_id}/voice_context",
    summary="Get conversation voice type and latest AI message",
    description="Retrieves the conversation voice type and latest AI message based on the provided message ID."
)
async def get_voice_context(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get conversation voice type and latest AI message for the conversation containing the specified message.
    
    This endpoint is particularly useful for audio playback in the mobile app, as it provides
    both the voice type to use and the latest AI message that might need to be played.
    """
    try:
        # Get message and validate
        message_object_id = ObjectId(message_id)
        message = db.messages.find_one({"_id": message_object_id})
        if not message:
            logger.warning(f"Message not found: {message_id}")
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Get conversation context using service
        conversation_id = str(message["conversation_id"])
        conversation_context = conversation_service.get_conversation_context(conversation_id)
        conversation = conversation_context["conversation"]
        messages = conversation_context["messages"]
        
        # Get the voice type from the conversation
        voice_type = conversation.get("voice_type", "hm_omega")
        
        # Find the latest AI message from the messages
        ai_messages = [msg for msg in messages if msg.get("sender") == "ai"]
        latest_ai_message_data = None
        
        if ai_messages:
            # Get the most recent AI message (messages are sorted by timestamp)
            latest_msg = ai_messages[-1]
            latest_ai_message_data = {
                "id": str(latest_msg["_id"]),
                "content": latest_msg.get("content", ""),
                "timestamp": latest_msg.get("timestamp", datetime.now().isoformat())
            }
        
        return {
            "voice_type": voice_type,
            "latest_ai_message": latest_ai_message_data,
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting voice context: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get voice context: {str(e)}"
        )


@router.get(
    "/messages/{message_id}/fallback_voice_context",
    summary="Get fallback voice context for any message ID",
    description="Provides voice context information without requiring the message to exist in the database."
)
async def get_fallback_voice_context(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get fallback voice context for any message ID without database validation.
    
    This endpoint is a reliable alternative to the /messages/{message_id}/voice_context endpoint
    when the message doesn't exist in the database. It always returns a valid response with
    the provided message ID as both the ID and content of the latest AI message.
    """
    logger.info(f"Fallback voice context requested for message_id: {message_id}")
    
    # Create a timestamp in the expected format
    timestamp = datetime.utcnow().isoformat()
    
    return {
        "voice_type": "jf_alpha",
        "latest_ai_message": {
            "id": message_id,
            "content": "Hello, how can I help you today?",
            "timestamp": timestamp
        }
    }


# POST /tts/synthesize - Synthesize text to speech (to be implemented)
# This endpoint will handle direct text-to-speech conversion

# GET /tts/voices - List available voices (to be implemented)
# This endpoint will return available TTS voices and their configurations 