import logging
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

import torch
import whisper
from app.utils.transcription_error_message import TranscriptionErrorMessages

logger = logging.getLogger(__name__)

@runtime_checkable
class SpeechToTextService(Protocol):
    """A protocol for speech-to-text services."""
    def transcribe(self, audio_file_path: Path, language_code: str = "en-US") -> str:
        """Transcribes an audio file."""
        ...

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

class WhisperSpeechService(SpeechToTextService):
    """Speech-to-text service using Whisper."""

    def transcribe(self, audio_file_path: Path, language_code: str = "en-US") -> str:
        """Transcribes audio using the Whisper model."""
        try:
            start_time = time.time()
            
            result = loaded_model.transcribe(str(audio_file_path), language=language_code)
            
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

def transcribe_file(audio_file: Path, language_code: str = "en-US", use_whisper: bool = True) -> str:
    """
    Transcribes an audio file using a primary service and falls back to another.
    """
    transcription = ""
    try:
        service = WhisperSpeechService() if use_whisper else GoogleSpeechToTextService()
        transcription = service.transcribe(audio_file, language_code)
    except Exception as e:
        logger.error(f"Primary transcription failed for {audio_file}: {e}")

    if not transcription:
        logger.info(f"Primary transcription was empty or failed, attempting fallback for {audio_file}")
        try:
            fallback_service = GoogleSpeechToTextService() if use_whisper else WhisperSpeechService()
            transcription = fallback_service.transcribe(audio_file, language_code)
        except Exception as fallback_e:
            logger.error(f"Fallback transcription failed for {audio_file}: {fallback_e}")
            return TranscriptionErrorMessages.DEFAULT_FALLBACK_ERROR.value
            
    if not transcription:
        return TranscriptionErrorMessages.EMPTY_TRANSCRIPTION.value
        
    return transcription 