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
from fastapi import HTTPException, UploadFile
from bson import ObjectId
import inspect

# Audio processing imports
import whisper
import torch
from threading import Lock
import google.generativeai as genai
from dotenv import load_dotenv

from app.repositories.audio_repository import AudioRepository
from app.models.audio import Audio
from app.utils.transcription_error_message import TranscriptionErrorMessages
from app.config.database import db

# Load environment variables
load_dotenv()

# Configure AI services
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

logger = logging.getLogger(__name__)

# Define valid audio file extensions
VALID_AUDIO_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac']
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class ModelPool:
    """Manages Whisper model instances for audio transcription."""
    
    def __init__(self):
        self.model_size = "tiny"
  
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
            # Validate the audio file
            self.validate_audio_file(file)
            
            # Save the file using internal method
            file_path, audio_model = self._save_audio_file_internal(file, user_id)
            audio_id = str(audio_model._id)
            
            self.logger.info(f"Successfully saved audio file for user {user_id}: {audio_id}")
            return audio_id
            
        except Exception as e:
            self.logger.error(f"Failed to save audio file for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save audio file: {str(e)}"
            )
    
    def _save_audio_file_internal(self, audio_file: UploadFile, user_id: str) -> Tuple[str, Audio]:
        """
        Internal method to save an audio file to disk and create a database record.
        
        Args:
            audio_file: The audio file to save
            user_id: ID of the user who owns the file
            
        Returns:
            Tuple containing the file path and Audio model
            
        Raises:
            Exception: If file saving fails
        """
        # Convert string user_id to ObjectId
        user_object_id = ObjectId(user_id)
        
        # Create user directory if it doesn't exist
        user_dir = UPLOAD_DIR / str(user_id)
        user_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = audio_file.filename or "unknown_file"
        safe_filename = f"{timestamp}_{filename.replace(' ', '_')}"
        file_path = user_dir / safe_filename
        
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        
        # Create audio record
        new_audio = Audio(
            user_id=user_object_id,
            filename=audio_file.filename,
            file_path=str(file_path),
            language="en-US"  # Default language
        )
        
        # Insert into database
        result = db.audio.insert_one(new_audio.to_dict())
        
        # Fetch the inserted audio
        created_audio = db.audio.find_one({"_id": result.inserted_id})
        
        # Store the _id value
        audio_id = created_audio["_id"]
        
        # Get the arguments that Audio.__init__ accepts
        audio_init_params = inspect.signature(Audio.__init__).parameters
        
        # Filter created_audio to only include fields accepted by Audio constructor
        filtered_audio_data = {}
        for key, value in created_audio.items():
            # Skip _id and created_at, which are automatically set in the constructor
            if key in audio_init_params and key not in ["_id", "created_at"]:
                filtered_audio_data[key] = value
        
        # Create Audio instance with filtered data
        audio_instance = Audio(**filtered_audio_data)
        audio_instance._id = audio_id  # Set the _id from database
        
        return str(file_path), audio_instance
    
    def validate_audio_file(self, file: UploadFile) -> bool:
        """
        Validate audio file format and size.
        
        Args:
            file (UploadFile): The audio file to validate
            
        Returns:
            bool: True if validation passes
            
        Raises:
            HTTPException: If validation fails
        """
        try:
            # Check if file is provided
            if not file:
                raise HTTPException(
                    status_code=400,
                    detail="No audio file provided"
                )
            
            # Check file extension
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in VALID_AUDIO_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid audio format. Supported formats: {', '.join(VALID_AUDIO_EXTENSIONS)}"
                )
            
            # Check file size if possible
            if hasattr(file.file, 'seek') and hasattr(file.file, 'tell'):
                file.file.seek(0, 2)  # Seek to end
                file_size = file.file.tell()
                file.file.seek(0)  # Reset to beginning
                
                if file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File size too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB"
                    )
            
            # Check filename length
            if len(file.filename) > 255:
                raise HTTPException(
                    status_code=400,
                    detail="Filename too long"
                )
            
            self.logger.debug(f"Audio file validation passed for: {file.filename}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Audio file validation error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {str(e)}"
            )
    
    def cleanup_temp_file(self, file_path: Optional[str]) -> None:
        """
        Clean up temporary files to prevent disk space issues.
        
        Args:
            file_path (Optional[str]): Path to the temporary file to delete
        """
        if file_path and Path(file_path).exists():
            try:
                Path(file_path).unlink()
                self.logger.debug(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temporary file {file_path}: {str(e)}")
    
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
            transcription, temp_file_path = self.transcribe_from_upload(file, language_code)
            self.logger.debug(f"Transcription completed with length: {len(transcription) if transcription else 0}")
            
            return transcription, temp_file_path
            
        except Exception as e:
            self.logger.error(f"Failed to transcribe audio: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Audio transcription failed: {str(e)}"
            )
    
    def transcribe_from_upload(self, audio_file: UploadFile, language_code: str = "en-US") -> Tuple[str, Path]:
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
            return TranscriptionErrorMessages.FALLBACK_ERROR.value
        except sr.UnknownValueError:
            logger.error("Speech recognition could not understand audio")
            return TranscriptionErrorMessages.EMPTY_TRANSCRIPTION.value
        except sr.RequestError as e:
            logger.error(f"Could not request results from Google Web Speech API; {str(e)}")
            return TranscriptionErrorMessages.FALLBACK_ERROR.value
        except Exception as e:
            logger.error(f"Error in local transcription: {str(e)}")
            return TranscriptionErrorMessages.FALLBACK_ERROR.value
    
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
            return TranscriptionErrorMessages.FALLBACK_ERROR.value
    
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
        return TranscriptionErrorMessages.FALLBACK_ERROR.value
    
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
            
            # Generate AI feedback
            feedback_data, _ = self.generate_feedback(transcription)
            
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
            audio_record = self.audio_repo.get_by_id(audio_id)
            if not audio_record:
                raise HTTPException(
                    status_code=404,
                    detail="Audio record not found"
                )
            
            metadata = {
                "id": str(audio_record._id),
                "filename": audio_record.filename,
                "user_id": str(audio_record.user_id),
                "language": audio_record.language,
                "created_at": audio_record.created_at.isoformat() if audio_record.created_at else None,
                "file_size": self._get_file_size(audio_record.file_path) if hasattr(audio_record, 'file_path') else None
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