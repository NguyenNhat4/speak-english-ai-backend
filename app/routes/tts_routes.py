from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any

from app.services.tts_service import TTSService
from app.utils.auth import get_current_user

router = APIRouter(
    prefix="/tts",
    tags=["tts"]
)

@router.get("/messages/{message_id}/speech", response_class=StreamingResponse)
async def get_ai_message_as_speech_stream( 
    message_id: str,
    tts_service: TTSService = Depends(),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves an AI message's text, converts it to speech, and streams the audio.
    """
    return await tts_service.get_speech_for_message(message_id)

@router.get("/demospeech", response_class=StreamingResponse)
async def get_demo_speech_stream(
    message: str = "Hello, this is a demonstration of the text to speech service.",
    tts_service: TTSService = Depends()
):
    """
    Generates a demo audio stream from the provided text.
    """
    return await tts_service.synthesize_demo_speech(message)

@router.get("/messages/{message_id}/voice_context", response_model=Dict[str, Any])
def get_voice_context(
    message_id: str,
    tts_service: TTSService = Depends(),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves the voice type and latest AI message for the associated conversation.
    """
    return tts_service.get_voice_context(message_id)

# POST /tts/synthesize - Synthesize text to speech (to be implemented)
# This endpoint will handle direct text-to-speech conversion

# GET /tts/voices - List available voices (to be implemented)
# This endpoint will return available TTS voices and their configurations 