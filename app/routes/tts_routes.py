from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Dict, Any

from app.services.tts_service import TTSService
from app.services import provider

router = APIRouter(
    prefix="/tts",
    tags=["tts"]
)

@router.get("/speech/{message_id}", response_class=StreamingResponse)
async def get_speech_for_message(
    message_id: str,
    tts_service: TTSService = Depends(provider.get_tts_service),
):
    """
    Generate speech for a specific AI message.
    """
    return await tts_service.get_speech_for_message(message_id)

@router.get("/voice-context/{message_id}", response_model=dict)
def get_voice_context(
    message_id: str,
    tts_service: TTSService = Depends(provider.get_tts_service)
):
    """
    Get voice context for a conversation based on a message ID.
    """
    return tts_service.get_voice_context(message_id)

@router.get("/demo-speech", response_class=StreamingResponse)
async def get_demo_speech(
    text: str = Query(..., min_length=1, max_length=250),
    tts_service: TTSService = Depends(provider.get_tts_service),
):
    """
    Generate a demo speech with a default voice.
    """
    return await tts_service.synthesize_demo_speech(text)

# POST /tts/synthesize - Synthesize text to speech (to be implemented)
# This endpoint will handle direct text-to-speech conversion

# GET /tts/voices - List available voices (to be implemented)
# This endpoint will return available TTS voices and their configurations 