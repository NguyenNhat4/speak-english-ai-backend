from fastapi import APIRouter, Depends, status, UploadFile, File
from typing import List

from app.schemas.audio import AudioResponse
from app.utils.auth import get_current_user
from app.services.audio_service import AudioService
from app.utils.dependencies import get_audio_service

router = APIRouter(
    prefix="/audio",
    tags=["audio"]
)

@router.post("/transcribe", response_model=dict)
def transcribe_audio(
    audio_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    audio_service: AudioService = Depends(get_audio_service),
):
    """
    Converts an uploaded audio file to text, saves it, and returns the result.
    """
    user_id = str(current_user["_id"])
    return audio_service.process_and_transcribe_audio(audio_file, user_id)

@router.get("/{audio_id}", response_model=AudioResponse)
def get_audio(
    audio_id: str,
    audio_service: AudioService = Depends(get_audio_service)
):
    """
    Get audio file metadata.
    """
    return audio_service.get_audio_metadata(audio_id)

@router.delete("/{audio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_audio(
    audio_id: str,
    current_user: dict = Depends(get_current_user),
    audio_service: AudioService = Depends(get_audio_service)
):
    """
    Delete an audio file and its record.
    """
    user_id = str(current_user["_id"])
    audio_service.delete_audio(audio_id, user_id)
    return None

# POST /audio/upload - Upload audio file (to be implemented)
# This endpoint will handle raw audio file uploads

# GET /audio/{audio_id} - Get audio file details (to be implemented)
# This endpoint will retrieve audio file metadata and transcription

# POST /audio/{audio_id}/transcribe - Transcribe specific audio (to be implemented)
# This endpoint will trigger transcription for a previously uploaded audio file

# DELETE /audio/{audio_id} - Delete audio file (to be implemented)
# This endpoint will handle audio file deletion and cleanup 