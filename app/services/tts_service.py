"""
TTS (Text-to-Speech) Service for handling TTS-related business logic.

This service manages text-to-speech conversion, voice selection,
and speech generation for the SpeakAI application.
"""

import logging
from typing import Dict, Any, Optional, Generator
from fastapi import HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.utils.tts_client_service import (
    get_speech_from_tts_service,
    pick_suitable_voice_name
)
from app.repositories.message_repository import MessageRepository
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)


class TTSService:
    """
    Service class for handling TTS business logic.
    
    This service acts as a wrapper around existing TTS utilities
    and provides a clean interface for text-to-speech operations.
    """
    
    def __init__(
        self,
        message_repo: MessageRepository = Depends(),
        conversation_service: ConversationService = Depends()
    ):
        """Initialize the TTS service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.message_repo = message_repo
        self.conversation_service = conversation_service
    
    async def get_speech_for_message(self, message_id: str) -> StreamingResponse:
        """
        Generates a speech audio stream for a given AI message.
        """
        message = self.message_repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        if message.get("sender") != "ai":
            raise HTTPException(status_code=400, detail="Speech can only be generated for AI messages")

        ai_text = message.get("content")
        if not ai_text:
            raise HTTPException(status_code=400, detail="AI Message has no text content to synthesize")

        conversation_id = str(message["conversation_id"])
        conversation_context = self.conversation_service.get_conversation_context(conversation_id)
        conversation_voice_type = conversation_context["conversation"].get("voice_type", "hm_omega")
        
        return await get_speech_from_tts_service(
            text_to_speak=ai_text,
            voice_name=conversation_voice_type,
            speed=1.3
        )

    async def synthesize_demo_speech(self, text: str) -> StreamingResponse:
        """
        Generates a demo speech stream with a default voice.
        """
        return await get_speech_from_tts_service(
            text_to_speak=text,
            voice_name="hm_omega", # Default demo voice
            speed=1.3
        )

    def get_voice_context(self, message_id: str) -> dict:
        """
        Retrieves voice context (voice type and latest AI message) for a conversation.
        """
        message = self.message_repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        conversation_id = str(message["conversation_id"])
        conversation_context = self.conversation_service.get_conversation_context(conversation_id)
        conversation = conversation_context["conversation"]
        messages = conversation_context["messages"]
        
        voice_type = conversation.get("voice_type", "hm_omega")
        
        ai_messages = [msg for msg in messages if msg.get("sender") == "ai"]
        latest_ai_message_data = None
        
        if ai_messages:
            latest_msg = ai_messages[-1]
            latest_ai_message_data = {
                "id": str(latest_msg["_id"]),
                "content": latest_msg.get("content", ""),
                "timestamp": latest_msg.get("timestamp")
            }
        
        return {
            "voice_type": voice_type,
            "latest_ai_message": latest_ai_message_data,
        }
    
    async def generate_speech_streaming(
        self,
        text: str,
        voice_name: Optional[str] = None,
        language_code: str = "en-US"
    ) -> StreamingResponse:
        """
        Generate streaming speech from text.
        
        Args:
            text (str): The text to convert to speech
            voice_name (Optional[str]): The voice name to use
            language_code (str): The language code for speech generation
            
        Returns:
            StreamingResponse: Streaming audio response
            
        Raises:
            HTTPException: If speech generation fails
        """
        try:
            if not text or not text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Text is required for speech generation"
                )
            
            # Use default voice if none provided
            if not voice_name:
                voice_name = "af_heart"  # Default voice
            
            # Generate streaming speech
            streaming_response = await get_speech_from_tts_service(
                text_to_speak=text,
                voice_name=voice_name,
                lang_code=language_code
            )
            
            self.logger.debug(f"Generated streaming speech for text length: {len(text)}")
            return streaming_response
            
        except Exception as e:
            self.logger.error(f"Failed to generate streaming speech: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Speech generation failed: {str(e)}"
            )
    
    async def generate_speech_with_context(
        self,
        text: str,
        conversation_context: Dict[str, Any],
        voice_name: Optional[str] = None
    ) -> StreamingResponse:
        """
        Generate speech with conversation context.
        
        Args:
            text (str): The text to convert to speech
            conversation_context (Dict[str, Any]): The conversation context
            voice_name (Optional[str]): The voice name to use
            
        Returns:
            StreamingResponse: Streaming audio response
            
        Raises:
            HTTPException: If speech generation fails
        """
        try:
            if not text or not text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Text is required for speech generation"
                )
            
            # Use default voice if none provided
            if not voice_name:
                voice_name = "af_heart"  # Default voice
            
            # Generate speech (the actual TTS service doesn't use context directly)
            streaming_response = await get_speech_from_tts_service(
                text_to_speak=text,
                voice_name=voice_name,
                lang_code="en-US"
            )
            
            self.logger.debug(f"Generated contextual speech for text length: {len(text)}")
            return streaming_response
            
        except Exception as e:
            self.logger.error(f"Failed to generate contextual speech: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Contextual speech generation failed: {str(e)}"
            )
    
    def select_suitable_voice(
        self,
        gender: str,
        language_code: str = "en-US"
    ) -> str:
        """
        Select a suitable voice based on gender and language.
        
        Args:
            gender (str): The desired gender (male/female)
            language_code (str): The language code
            
        Returns:
            str: The selected voice name
            
        Raises:
            HTTPException: If voice selection fails
        """
        try:
            if not gender or gender.lower() not in ['male', 'female']:
                raise HTTPException(
                    status_code=400,
                    detail="Valid gender (male/female) is required"
                )
            
            voice_name = pick_suitable_voice_name(gender)
            
            self.logger.debug(f"Selected voice '{voice_name}' for gender: {gender}")
            return voice_name
            
        except Exception as e:
            self.logger.error(f"Failed to select suitable voice: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Voice selection failed: {str(e)}"
            )
    
    def create_streaming_response(
        self,
        audio_stream: Generator[bytes, None, None],
        filename: str = "speech.mp3"
    ) -> StreamingResponse:
        """
        Create a streaming response for audio data.
        
        Args:
            audio_stream (Generator[bytes, None, None]): The audio stream
            filename (str): The filename for the response
            
        Returns:
            StreamingResponse: The streaming response object
        """
        try:
            return StreamingResponse(
                audio_stream,
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Cache-Control": "no-cache"
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create streaming response: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create audio response: {str(e)}"
            ) 