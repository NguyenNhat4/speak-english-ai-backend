"""
Audio Repository Implementation

This module provides specialized repository operations for audio data,
extending the base repository with audio-specific methods.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import HTTPException

from app.repositories.base_repository import BaseRepository
from app.models.audio import Audio

logger = logging.getLogger(__name__)


class AudioRepository(BaseRepository[Audio]):
    """
    Repository class for handling audio database operations.
    
    This class extends BaseRepository to provide audio-specific
    database operations while maintaining consistency with the repository pattern.
    """
    
    def __init__(self):
        """Initialize the audio repository."""
        super().__init__("audio", Audio)
    
    def create_audio(self, user_id: str, url: Optional[str] = None, filename: Optional[str] = None,
                    file_path: Optional[str] = None, duration_seconds: Optional[float] = None,
                    transcription: Optional[str] = None, language: str = "en-US") -> Dict[str, Any]:
        """
        Create a new audio record.
        
        Args:
            user_id: String representation of the user ID
            url: Optional URL where audio is stored
            filename: Optional original filename
            file_path: Optional local file path
            duration_seconds: Optional duration in seconds
            transcription: Optional transcription text
            language: Language of the audio content
            
        Returns:
            Created audio document
        """
        try:
            # Convert user_id to ObjectId
            user_object_id = ObjectId(user_id)
            
            # Create audio model instance
            audio = Audio(
                user_id=user_object_id,
                url=url,
                filename=filename,
                file_path=file_path,
                duration_seconds=duration_seconds,
                transcription=transcription,
                language=language
            )
            
            return self.create(audio.to_dict())
            
        except Exception as e:
            self.logger.error(f"Error creating audio: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create audio: {str(e)}"
            )
    
    def get_user_audio(self, user_id: str, skip: int = 0, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all audio records for a user.
        
        Args:
            user_id: String representation of the user ID
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            
        Returns:
            List  of user's audio records
        """
        try:
            user_object_id = ObjectId(user_id)
            
            filter_dict =  {"user_id": user_object_id}
            sort = [("created_at", -1)]
            
            return self.find_all(
                filter_dict=filter_dict,
                skip=skip,
                limit=limit,
                sort=sort
            )
            
        except Exception as e:
            self.logger.error(f"Error getting user audio: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user ID or query failed: {str(e)}"
            )
    
    def update_transcription(self, audio_id: str, transcription: str) -> Optional[Dict[str, Any]]:
        """
        Update audio record with transcription.
        
        Args:
            audio_id: String representation of the audio ID
            transcription: Transcription text
            
        Returns:
            Updated audio document
        """
        try:
            update_data = {"transcription": transcription}
            return self.update(audio_id, update_data)
            
        except Exception as e:
            self.logger.error(f"Error updating transcription: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update transcription: {str(e)}"
            )
    
    def update_feedback(self, audio_id: str, pronunciation_score: Optional[float] = None,
                       pronunciation_feedback: Optional[Dict[str, Any]] = None,
                       language_feedback: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Update audio record with feedback data.
        
        Args:
            audio_id: String representation of the audio ID
            pronunciation_score: Optional pronunciation score
            pronunciation_feedback: Optional pronunciation feedback
            language_feedback: Optional language feedback
            
        Returns:
            Updated audio document
        """
        try:
            update_data = {}
            if pronunciation_score is not None:
                update_data["pronunciation_score"] = pronunciation_score
            if pronunciation_feedback is not None:
                update_data["pronunciation_feedback"] = pronunciation_feedback
            if language_feedback is not None:
                update_data["language_feedback"] = language_feedback
            
            return self.update(audio_id, update_data)
            
        except Exception as e:
            self.logger.error(f"Error updating audio feedback: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update audio feedback: {str(e)}"
            )
    
    def get_audio_by_language(self, language: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get audio records by language.
        
        Args:
            language: Language to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            List of audio records in the specified language
        """
        try:
            filter_dict = {"language": language}
            
            if user_id:
                user_object_id = ObjectId(user_id)
                filter_dict["user_id"] = user_object_id
            
            sort = [("created_at", -1)]
            
            return self.find_all(filter_dict=filter_dict, sort=sort)
            
        except Exception as e:
            self.logger.error(f"Error getting audio by language: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get audio by language: {str(e)}"
            ) 