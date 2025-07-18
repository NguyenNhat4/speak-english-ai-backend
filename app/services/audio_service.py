"""
Audio Service for handling all audio processing business logic.

This service manages all audio-related operations including file operations, 
transcription, validation, feedback processing, and AI-powered language analysis.
"""

import logging
import os
import shutil
import tempfile
import json
import time
from typing import Dict, Any, Optional, Tuple, List, Protocol, runtime_checkable
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException, UploadFile, Depends
from bson import ObjectId
import inspect
import torch
import whisper

from app.repositories.audio_repository import AudioRepository
from app.models.audio import Audio
from app.utils.transcription_error_message import TranscriptionErrorMessages
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Language mapping for Whisper
WHISPER_LANGUAGE_MAPPING = {
    "en-US": "english",
    "vi-VN": "vietnamese",
}

# Import file utilities
from app.utils.file_utils import (
    validate_audio_file,
    save_uploaded_file,
    cleanup_temp_file,
    create_temp_file,
    get_file_size,
    UPLOAD_DIR
)


@runtime_checkable
class SpeechToTextService(Protocol):
    """A protocol for speech-to-text services."""
    def transcribe(self, audio_file_path: Path, language_code: str = "en-US") -> str:
        """Transcribes an audio file."""
        ...

class WhisperSpeechService(SpeechToTextService):
    """Speech-to-text service using Whisper."""
    def __init__(self, model):
        self.model = model

    def transcribe(self, audio_file_path: Path, language_code: str = "en-US") -> str:
        """Transcribes audio using the Whisper model."""
        try:
            start_time = time.time()
            language = WHISPER_LANGUAGE_MAPPING.get(language_code, "english")  # Default to English
            result = self.model.transcribe(str(audio_file_path), language=language)
            end_time = time.time()
            logger.info(f"Whisper transcription took {end_time - start_time:.2f} seconds")
            return result.get("text", "").strip()
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            raise

class GoogleSpeechToTextService(SpeechToTextService):
    """Speech-to-text service using Google Cloud Speech-to-Text as a fallback."""

    def transcribe(self, audio_file_path: Path, language_code: str = "en-US") -> str:
        """Transcribes audio using Google Cloud Speech-to-Text."""
        try:
            from google.cloud import speech
            
            client = speech.SpeechClient()
            
            with open(audio_file_path, "rb") as audio_file_content:
                content = audio_file_content.read()
            
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(language_code=language_code)
            
            response = client.recognize(config=config, audio=audio)
            return " ".join([res.alternatives[0].transcript for res in response.results]).strip()
                
        except Exception as e:
            logger.warning(f"Google Cloud Speech-to-Text transcription failed: {str(e)}")
            raise


class AudioService:
    """
    Comprehensive service class for handling all audio processing business logic.
    
    This service encapsulates all audio-related operations including:
    - File saving and validation
    - Transcription using multiple methods (Whisper, Speech Recognition)
    - AI-powered feedback generation
    - Temporary file management
    - Error handling and fallback mechanisms
    """
    
    def __init__(self, audio_repo: Optional[AudioRepository] = None):
        """
        Initialize the audio service with repository dependency.
        
        Args:
            audio_repo: AudioRepository instance
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.upload_dir = Path("app/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.audio_repo = audio_repo or AudioRepository()
        self.whisper_model = self._load_whisper_model()
    
    def _load_whisper_model(self):
        model_size = "large-v3-turbo"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            logger.info(f"GPU device: {torch.cuda.get_device_name(0)}")
        return whisper.load_model(model_size, device=device)

    def _transcribe_file(self, audio_file: Path, language_code: str = "en-US", use_whisper: bool = True) -> str:
        """
        Transcribes an audio file using a primary service and falls back to another.
        """
        transcription = ""
        try:
            primary_service = WhisperSpeechService(self.whisper_model) if use_whisper else GoogleSpeechToTextService()
            transcription = primary_service.transcribe(audio_file, language_code)
        except Exception as e:
            logger.error(f"Primary transcription failed for {audio_file}: {e}")

        if not transcription:
            logger.info(f"Primary transcription was empty or failed, attempting fallback for {audio_file}")
            try:
                fallback_service = GoogleSpeechToTextService() if use_whisper else WhisperSpeechService(self.whisper_model)
                transcription = fallback_service.transcribe(audio_file, language_code)
            except Exception as fallback_e:
                logger.error(f"Fallback transcription failed for {audio_file}: {fallback_e}")
                return TranscriptionErrorMessages.DEFAULT_FALLBACK_ERROR.value
                
        if not transcription:
            return TranscriptionErrorMessages.EMPTY_TRANSCRIPTION.value
            
        return transcription

    def process_and_transcribe_audio(self, file: UploadFile, user_id: str, language_code: str = "en-US") -> dict:
        """
        Orchestrates the audio processing pipeline: transcription, saving, and cleanup.
        """
        try:
            # Step 1: Transcribe the audio file
            transcription, temp_file_path = self.transcribe_audio(file, language_code)
            
            # Step 2: Check if transcription was successful
            if transcription and transcription.strip() and transcription != TranscriptionErrorMessages.EMPTY_TRANSCRIPTION.value:
                try:
                    # Reset file pointer before saving
                    file.file.seek(0)
                    audio_id = self.save_audio_file(file, user_id, language_code)
                    
                    cleanup_temp_file(temp_file_path)
                    
                    return {
                        "audio_id": audio_id,
                        "transcription": transcription,
                        "success": True
                    }
                except Exception as e:
                    self.logger.error(f"Error saving audio after successful transcription: {str(e)}")
                    cleanup_temp_file(temp_file_path)
                    return {
                        "audio_id": None,
                        "transcription": transcription,
                        "success": True,
                        "warning": "Transcription successful but audio storage failed"
                    }
            else:
                cleanup_temp_file(temp_file_path)
                return {
                    "audio_id": None,
                    "transcription": "No speech detected in audio file",
                    "success": False
                }
        except Exception as e:
            self.logger.error(f"Error in audio processing pipeline: {str(e)}")
            # In case of a failure in transcription, temp_file_path might not exist
            # but we can try to clean it up just in case.
            if 'temp_file_path' in locals() and temp_file_path:
                cleanup_temp_file(temp_file_path)
            raise HTTPException(
                status_code=500,
                detail=f"Error processing audio file: {str(e)}"
            )

    # =============================================================================
    # FILE MANAGEMENT METHODS
    # =============================================================================
    
    def save_audio_file(self, file: UploadFile, user_id: str, language_code: str = "en-US") -> str:
        """
        Save an audio file to storage and create database record.
        
        Args:
            file (UploadFile): The audio file to save
            user_id (str): The ID of the user uploading the file
            language_code (str): The language code of the audio file
            
        Returns:
            str: The ID of the saved audio record
            
        Raises:
            HTTPException: If file saving fails
        """
        try:
            # Save the file using centralized utility
            file_path = save_uploaded_file(file, user_id, "audio")
            
            # Create audio record via the repository
            created_audio = self.audio_repo.create_audio(
                user_id=user_id,
                filename=file.filename,
                file_path=str(file_path),
                language=language_code
            )
            
            # The audio_id is now part of the returned model from the repo
            audio_id = str(created_audio['_id'])
            
            self.logger.info(f"Successfully saved audio file for user {user_id}: {audio_id}")
            return audio_id
            
        except Exception as e:
            self.logger.error(f"Failed to save audio file for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save audio file: {str(e)}"
            )
    
    def delete_audio(self, audio_id: str, user_id: str):
        """
        Deletes an audio file record and the physical file.
        """
        audio_record = self.audio_repo.find_by_id(audio_id)
        if not audio_record:
            raise HTTPException(status_code=404, detail="Audio record not found")

        # Optional: Check if the user is authorized to delete this file
        if str(audio_record['user_id']) != user_id:
            raise HTTPException(status_code=403, detail="User not authorized to delete this audio file")

        # Delete file from storage
        try:
            file_path = Path(audio_record['file_path'])
            if file_path.exists():
                os.remove(file_path)
                self.logger.info(f"Deleted audio file: {file_path}")
        except Exception as e:
            # Log error but proceed to delete DB record
            self.logger.error(f"Error deleting audio file {audio_record['file_path']}: {e}")

        # Delete record from database
        deleted = self.audio_repo.delete(audio_id)
        if not deleted:
            # This might happen if there's a race condition, but it's good to handle.
            raise HTTPException(status_code=404, detail="Audio record could not be deleted from database")
        
        return {"message": "Audio file deleted successfully"}
    
    # Validation is now handled by file_utils.validate_audio_file
    
    # cleanup_temp_file is now handled by file_utils.cleanup_temp_file
    
    # =============================================================================
    # TRANSCRIPTION METHODS
    # =============================================================================
    
    def transcribe_audio(self, file: UploadFile, language_code: str = "en-US") -> Tuple[str, Optional[str]]:
        """
        Transcribe audio file to text using the optimal method.
        
        Args:
            file (UploadFile): The audio file to transcribe
            language_code (str): Language code for transcription
            
        Returns:
            Tuple[str, Optional[str]]: Transcription text and temporary file path
            
        Raises:
            HTTPException: If transcription fails
        """
        temp_file_path = None
        try:
            # Create temporary file and transcribe
            temp_file_path = create_temp_file(file)
            transcription = self._transcribe_file(temp_file_path, language_code)
            self.logger.debug(f"Transcription completed with length: {len(transcription) if transcription else 0}")
            
            return transcription, str(temp_file_path)
            
        except Exception as e:
            self.logger.error(f"Failed to transcribe audio: {str(e)}")
            if temp_file_path:
                cleanup_temp_file(str(temp_file_path))
            raise HTTPException(
                status_code=500,
                detail=f"Audio transcription failed: {str(e)}"
            )

    def get_audio_metadata(self, audio_id: str) -> Dict[str, Any]:
        """
        Get metadata for an audio file.
        
        Args:
            audio_id (str): The ID of the audio record
            
        Returns:
            Dict[str, Any]: Audio metadata
            
        Raises:
            HTTPException: If audio not found
        """
        try:
            audio_record = self.audio_repo.find_by_id(audio_id)
            if not audio_record:
                raise HTTPException(
                    status_code=404,
                    detail="Audio record not found"
                )
            
            file_path = audio_record.get("file_path")
            file_size = self._get_file_size(file_path) if file_path else None
            created_at = audio_record.get('created_at')
            user_id = audio_record.get("user_id")

            metadata = {
                "id": audio_record.get("id"),
                "filename": audio_record.get("filename"),
                "user_id": str(user_id) if user_id else None,
                "language": audio_record.get("language"),
                "created_at": created_at.isoformat() if created_at else None,
                "file_size": file_size
            }
            
            return metadata
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get audio metadata: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve audio metadata"
            )

    def _get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size in bytes."""
        try:
            return Path(file_path).stat().st_size
        except:
            return None 