"""
TTS (Text-to-Speech) Service for handling TTS-related business logic.

This service manages text-to-speech conversion, voice selection,
and speech generation for the SpeakAI application.
"""

import logging
from typing import Dict, Any, Optional, Generator
from fastapi import HTTPException, Depends
from fastapi.responses import StreamingResponse
import httpx
import random

from app.config.settings import settings
from app.repositories.message_repository import MessageRepository
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

MALE_VOICES = ["im_nicola", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_v0adam", "hm_omega", "bm_daniel", "bm_fable", "bm_george", "bm_lewis", "bm_v0george", "bm_v0lewis"]
FEMALE_VOICES = ["af_aoede", "af_heart", "bf_v0isabella"]

class TTSService:
    """
    Service class for handling TTS business logic.
    
    This service acts as a wrapper around existing TTS utilities
    and provides a clean interface for text-to-speech operations.
    """
    
    def __init__(
        self,
        message_repo: Optional[MessageRepository] = None,
        conversation_service: Optional[ConversationService] = None
    ):
        """Initialize the TTS service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.message_repo = message_repo or MessageRepository()
        self.conversation_service = conversation_service or ConversationService()
        self.tts_backend_base_url = settings.tts_backend_base_url
    
    async def _get_speech_from_tts_service(
        self,
        text_to_speak: str,
        voice_name: str,
        response_format: str = "mp3",
        speed: float = 1.2,
        lang_code: str = "en-US"
    ):
        """
        Calls the external TTS Service to convert text to speech and streams the audio.
        """
        tts_request_url = f"{self.tts_backend_base_url}/v1/audio/speech"
        payload = {
            "model": "kokoro",
            "input": text_to_speak,
            "voice": voice_name,
            "response_format": response_format,
            "download_format": response_format,
            "speed": speed,
            "stream": True,
            "return_download_link": False,
            "lang_code": lang_code,
            "normalization_options": {
                "normalize": True,
                "unit_normalization": False,
                "url_normalization": True,
                "email_normalization": True,
                "optional_pluralization_normalization": True,
                "phone_normalization": True
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": f"audio/{response_format}" if response_format != "pcm" else "application/octet-stream"
        }
        if response_format == "mp3":
            headers["Accept"] = "audio/mpeg"

        client = httpx.AsyncClient(timeout=60.0)
        response_stream = None
        try:
            request = client.build_request("POST", tts_request_url, json=payload, headers=headers)
            response_stream = await client.send(request, stream=True)

            if response_stream.status_code != 200:
                error_content = await response_stream.aread()
                error_detail = f"TTS Service error ({response_stream.status_code}): {error_content.decode()}"
                raise HTTPException(status_code=response_stream.status_code, detail=error_detail)
            
            async def generator_func(current_response, client_to_close):
                try:
                    async for chunk in current_response.aiter_bytes():
                        yield chunk
                except httpx.StreamClosed as e:
                    logger.warning(f"TTS stream was closed gracefully: {e}")
                except Exception as e:
                    logger.error(f"An error occurred during TTS streaming: {e}", exc_info=True)
                finally:
                    if current_response and not current_response.is_closed:
                        await current_response.aclose()
                    if client_to_close:
                        await client_to_close.aclose()

            media_type = response_stream.headers.get("content-type", "audio/mpeg")
            return StreamingResponse(generator_func(response_stream, client), media_type=media_type)

        except (httpx.TimeoutException, httpx.RequestError) as e:
            if response_stream and not response_stream.is_closed:
                await response_stream.aclose()
            await client.aclose()
            status_code = 504 if isinstance(e, httpx.TimeoutException) else 503
            raise HTTPException(status_code=status_code, detail=f"TTS Service communication error: {str(e)}")
        except Exception as e:
            if response_stream and not response_stream.is_closed:
                await response_stream.aclose()
            await client.aclose()
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=f"Unexpected error during TTS request: {str(e)}")

    def _pick_suitable_voice_name(self, gender: str) -> str:
        """   
        Returns a random voice name based on the specified gender.
        """
        if "f" in gender.lower():
            return random.choice(FEMALE_VOICES)
        return random.choice(MALE_VOICES)
    
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
        
        return await self._get_speech_from_tts_service(
            text_to_speak=ai_text,
            voice_name=conversation_voice_type,
            speed=1.3
        )

    async def synthesize_demo_speech(self, text: str) -> StreamingResponse:
        """
        Generates a demo speech stream with a default voice.
        """
        return await self._get_speech_from_tts_service(
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
            streaming_response = await self._get_speech_from_tts_service(
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
            streaming_response = await self._get_speech_from_tts_service(
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
            
            voice_name = self._pick_suitable_voice_name(gender)
            
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