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
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException, UploadFile, Depends
from bson import ObjectId
import inspect

# Audio processing imports
import whisper
import torch
from threading import Lock

from app.repositories.audio_repository import AudioRepository
from app.models.audio import Audio
from app.utils.transcription_error_message import TranscriptionErrorMessages
from app.config.database import db
from app.config.settings import settings
from app.utils.gemini import gemini_model

logger = logging.getLogger(__name__)

# Import file utilities
from app.utils.file_utils import (
    validate_audio_file,
    save_uploaded_file,
    cleanup_temp_file,
    create_temp_file,
    get_file_size,
    UPLOAD_DIR
)


class ModelPool:
    """Manages Whisper model instances for audio transcription."""
    
    def __init__(self):
        self.model_size = "large-v3-turbo"
  
    def get_model(self):
        device = self.get_device()
        model = whisper.load_model(self.model_size, device=device)
        return model
        
    def get_device(self):
        cuda_available = torch.cuda.is_available()
        
        if cuda_available:
            device = "cuda"
            logger.info(f"GPU device: {torch.cuda.get_device_name(0)}")
        else:
            device = "cpu"
            
        return device


# Initialize model pool and load model
model_pool = ModelPool()
loaded_model = model_pool.get_model()


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
    
    def process_and_transcribe_audio(self, file: UploadFile, user_id: str) -> dict:
        """
        Orchestrates the audio processing pipeline: transcription, saving, and cleanup.
        """
        try:
            # Step 1: Transcribe the audio file
            transcription, temp_file_path = self.transcribe_audio(file)
            
            # Step 2: Check if transcription was successful
            if transcription and transcription.strip() and transcription != TranscriptionErrorMessages.EMPTY_TRANSCRIPTION.value:
                try:
                    # Reset file pointer before saving
                    file.file.seek(0)
                    audio_id = self.save_audio_file(file, user_id)
                    
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
    
    def save_audio_file(self, file: UploadFile, user_id: str) -> str:
        """
        Save an audio file to storage and create database record.
        
        Args:
            file (UploadFile): The audio file to save
            user_id (str): The ID of the user uploading the file
            
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
                language="en-US"  # Default language
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
        try:
            # Create temporary file and transcribe
            transcription, temp_file_path_obj = self.transcribe_from_upload(file, language_code)
            self.logger.debug(f"Transcription completed with length: {len(transcription) if transcription else 0}")
            
            temp_file_path = str(temp_file_path_obj) if temp_file_path_obj else None
            return transcription, temp_file_path
            
        except Exception as e:
            self.logger.error(f"Failed to transcribe audio: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Audio transcription failed: {str(e)}"
            )
    
    def transcribe_from_upload(self, audio_file: UploadFile, language_code: str = "en-US") -> Tuple[str, Optional[Path]]:
        """
        Create a temporary file from upload and transcribe it without storing in DB first.
        
        This optimized method creates a temporary file, transcribes it, and returns the
        transcription without adding it to the database until we know transcription was successful.
        
        Args:
            audio_file: The audio file from the upload
            language_code: Language code for transcription (default: en-US)
            
        Returns:
            A tuple containing (transcription text, temporary file path)
            
        Raises:
            Exception: If transcription fails
        """
        try:
            # Create a temporary file with the same extension as the uploaded file
            filename = audio_file.filename or "unknown_file"
            _, ext = os.path.splitext(filename)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                # Copy uploaded file to temporary file
                shutil.copyfileobj(audio_file.file, tmp_file)
                tmp_path = Path(tmp_file.name)
            
            # Make sure we reset the file pointer for potential future use
            audio_file.file.seek(0)
            
            # Transcribe the temporary file
            transcription = self.transcribe_audio_file(tmp_path, language_code)
            
            # Return both the transcription and the path to the temporary file
            return transcription, tmp_path
            
        except Exception as e:
            logger.error(f"Error transcribing from upload: {str(e)}")
            # Return the error message and None for the file path
            return self._try_fallback_transcription(Path(""), language_code), None
    
    def transcribe_audio_file(self, audio_file: Path, language_code: str = "en-US", use_whisper: bool = True) -> str:
        """
        Transcribe audio file to text using the appropriate service.
        
        Args:
            audio_file: Path to the audio file to transcribe
            language_code: Language code for transcription (default: en-US)
            use_whisper: Whether to use Whisper model (default: True)
            
        Returns:
            Transcription text
            
        Raises:
            Exception: If transcription fails
        """
        try:
            transcription_text = ""
            if not use_whisper:
                # Use local transcription service
                transcription_text = self.transcribe_audio_local(audio_file, language_code)
            else:
                transcription_text = self.transcribe_audio_with_whisper(audio_file, language_code)
                
            return transcription_text if transcription_text and len(transcription_text) > 0 else TranscriptionErrorMessages.EMPTY_TRANSCRIPTION.value
            
        except Exception as e:
            logger.error(f"Error in audio transcription: {str(e)}")
            return self._try_fallback_transcription(audio_file, language_code)
    
    def transcribe_audio_local(self, audio_file_path: Path, language_code: str = "en-US") -> str:
        """
        Transcribe audio using local SpeechRecognition library.
        
        This function converts spoken words in an audio file into text using Google's
        Web Speech API through the SpeechRecognition library. It handles various exceptions
        that may occur during the transcription process.
        
        Args:
            audio_file_path: Path to the audio file
            language_code: Language code (default: en-US)
            
        Returns:
            Transcription text
        """
        try:
            import speech_recognition as sr
            
            # Initialize recognizer
            r = sr.Recognizer()
            
            # Load audio file
            with sr.AudioFile(str(audio_file_path)) as source:
                # Read the audio data
                audio_data = r.record(source)
                
                # Recognize speech using Google Web Speech API (free)
                text = r.recognize_google(audio_data, language=language_code)
                
                return text
        
        except ImportError:
            logger.error("SpeechRecognition library not installed. Please install it with: pip install SpeechRecognition")
            return TranscriptionErrorMessages.DEFAULT_FALLBACK_ERROR.value
        except sr.UnknownValueError:
            logger.error("Speech recognition could not understand audio")
            return TranscriptionErrorMessages.EMPTY_TRANSCRIPTION.value
        except sr.RequestError as e:
            logger.error(f"Could not request results from Google Web Speech API; {str(e)}")
            return TranscriptionErrorMessages.DEFAULT_FALLBACK_ERROR.value
        except Exception as e:
            logger.error(f"Error in local transcription: {str(e)}")
            return TranscriptionErrorMessages.DEFAULT_FALLBACK_ERROR.value
    
    def transcribe_audio_with_whisper(self, audio_file_path: Path, language_code: str = "en-US") -> str:
        """
        Transcribe audio using Whisper model.
        
        This function uses the Whisper model to transcribe spoken words in an audio file into text.
        It handles various exceptions that may occur during the transcription process.
        
        Args:
            audio_file_path: Path to the audio file
            language_code: Language code (default: en-US)
            
        Returns:
            Transcription text
        """
        try:
            logger.info(f"Model used: {model_pool.model_size}")
           
            # Convert language code
            if 'us' in language_code.lower():
                language_code = "en"
            else:
                language_code = "vi"
                
            transcribe_options = {
                "language": language_code,
                "task": "transcribe",
            }
            result = loaded_model.transcribe(str(audio_file_path), language=language_code)
            return result["text"]
            
        except Exception as e:
            logger.error(f"Error in Whisper transcription: {str(e)}")
            return TranscriptionErrorMessages.DEFAULT_FALLBACK_ERROR.value
    
    def _try_fallback_transcription(self, audio_file: Path, language_code: str = "en-US") -> str:
        """
        Attempt to transcribe using alternative methods when the primary method fails.
        
        Args:
            audio_file: Path to the audio file to transcribe
            language_code: Language code for transcription (default: en-US)
            
        Returns:
            Transcription text or a default message if all methods fail
        """
        try:
            # Try to use an external API service like Google Cloud Speech-to-Text
            from google.cloud import speech
            
            client = speech.SpeechClient()
            
            with open(audio_file, "rb") as audio_file_content:
                content = audio_file_content.read()
            
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language_code,
            )
            
            response = client.recognize(config=config, audio=audio)
            transcription = " ".join([result.alternatives[0].transcript for result in response.results])
            
            if transcription and transcription.strip():
                return transcription
                
        except Exception as e:
            logger.warning(f"Fallback transcription failed: {str(e)}")
        
        # If all else fails, return a default message
        return TranscriptionErrorMessages.DEFAULT_FALLBACK_ERROR.value
    
    # =============================================================================
    # FEEDBACK AND AI PROCESSING METHODS
    # =============================================================================
    
    
    def process_audio_for_feedback(
        self, 
        transcription: str, 
        user_id: str, 
        conversation_id: str,
        audio_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        DEPRECATED: This method is outdated. Use FeedbackService to generate feedback.
        Process audio transcription for feedback generation.
        
        Args:
            transcription (str): The transcribed text from audio
            user_id (str): The ID of the user
            conversation_id (str): The ID of the conversation
            audio_id (Optional[str]): The ID of the audio record
            
        Returns:
            Dict[str, Any]: Processing results and feedback data
            
        Raises:
            HTTPException: If processing fails
        """
        try:
            # Validate inputs
            if not transcription or not transcription.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Empty transcription provided"
                )
            
            if not ObjectId.is_valid(user_id):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid user ID format"
                )
            
            if not ObjectId.is_valid(conversation_id):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid conversation ID format"
                )
            
            # TODO: Refactor or remove this method.
            # The feedback generation logic has been moved to FeedbackService.
            # feedback_data, _ = self.generate_feedback(transcription)
            feedback_data = {} # Placeholder
            
            # Prepare processing results
            processing_results = {
                "transcription": transcription,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "audio_id": audio_id,
                "feedback": feedback_data,
                "processed_at": datetime.utcnow().isoformat(),
                "status": "success"
            }
            
            self.logger.info(f"Successfully processed audio feedback for user {user_id}")
            return processing_results
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to process audio for feedback: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Audio feedback processing failed: {str(e)}"
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