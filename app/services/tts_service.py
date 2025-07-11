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

from app.config.settings import settings
from app.repositories.message_repository import MessageRepository
from app.repositories.conversation_repository import ConversationRepository
from app.utils.voice_utils import pick_suitable_voice_name
from app.schemas.tts import VoiceContextResponse, LatestAIMessage

logger = logging.getLogger(__name__)

class TTSService:
    """
    Service class for handling TTS business logic.
    
    This service acts as a wrapper around existing TTS utilities
    and provides a clean interface for text-to-speech operations.
    """
    
    def __init__(
        self,
        message_repo: Optional[MessageRepository] = None,
        conversation_repo: Optional[ConversationRepository] = None
    ):
        """Initialize the TTS service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.message_repo = message_repo or MessageRepository()
        self.conversation_repo = conversation_repo or ConversationRepository()
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
        conversation = self.conversation_repo.find_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        conversation_voice_type = conversation.get("voice_type", "hm_omega")
        
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

    def get_voice_context(self, message_id: str) -> VoiceContextResponse:
        """
        Retrieves voice context (voice type and latest AI message) for a conversation.
        """
        message = self.message_repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        conversation_id = str(message["conversation_id"])
        conversation = self.conversation_repo.find_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        messages = self.message_repo.get_messages_by_conversation(conversation_id)
        
        voice_type = conversation.get("voice_type", "hm_omega")
        
        ai_messages = [msg for msg in messages if msg.get("sender") == "ai"]
        latest_ai_message_obj = None
        
        if ai_messages:
            latest_msg_data = ai_messages[-1]
            latest_ai_message_obj = LatestAIMessage.model_validate(latest_msg_data)
        
        return VoiceContextResponse(
            voice_type=voice_type,
            latest_ai_message=latest_ai_message_obj,
        )
    
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
            
            # Use voice from context if available, otherwise use default
            if not voice_name:
                voice_name = conversation_context.get("voice_type")
            if not voice_name:
                voice_name = "af_heart"
            
            # Generate streaming speech
            streaming_response = await self._get_speech_from_tts_service(
                text_to_speak=text,
                voice_name=voice_name
            )
            
            self.logger.debug(f"Generated speech with context for text length: {len(text)}")
            return streaming_response
            
        except Exception as e:
            self.logger.error(f"Failed to generate speech with context: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Speech generation with context failed: {str(e)}"
            )
    
    def create_streaming_response(
        self,
        audio_stream: Generator[bytes, None, None],
        filename: str = "speech.mp3"
    ) -> StreamingResponse:
        """
        Create a streaming response for the audio stream.
        
        Args:
            audio_stream (Generator[bytes, None, None]): The audio stream generator
            filename (str): The filename for the streaming response
            
        Returns:
            StreamingResponse: The streaming response for the audio
        """
        response = StreamingResponse(
            audio_stream,
            media_type="audio/mpeg"
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response 