"""
Dependency injection utilities for FastAPI routes.

This module provides centralized dependency injection to eliminate
repetitive service instantiation across routes.
"""

from typing import Generator
from app.services.audio_service import AudioService
from app.services.conversation_service import ConversationService
from app.services.feedback_service import FeedbackService
from app.services.ai_service import AIService
from app.services.user_service import UserService
from app.services.message_service import MessageService
from app.services.tts_service import TTSService
from app.repositories.audio_repository import AudioRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository


def get_audio_service() -> AudioService:
    """Get AudioService instance."""
    return AudioService()


def get_conversation_service() -> ConversationService:
    """Get ConversationService instance."""
    return ConversationService()


def get_feedback_service() -> FeedbackService:
    """Get FeedbackService instance."""
    return FeedbackService()


def get_message_service() -> MessageService:
    """Get MessageService instance."""
    return MessageService()


def get_tts_service() -> TTSService:
    """Get TTSService instance."""
    return TTSService()


def get_ai_service() -> AIService:
    """Get AIService instance."""
    return AIService()


def get_user_service() -> UserService:
    """Get UserService instance."""
    return UserService()


def get_audio_repository() -> AudioRepository:
    """Get AudioRepository instance."""
    return AudioRepository()


def get_conversation_repository() -> ConversationRepository:
    """Get ConversationRepository instance."""
    return ConversationRepository()


def get_feedback_repository() -> FeedbackRepository:
    """Get FeedbackRepository instance."""
    return FeedbackRepository()


def get_message_repository() -> MessageRepository:
    """Get MessageRepository instance."""
    return MessageRepository()


def get_user_repository() -> UserRepository:
    """Get UserRepository instance."""
    return UserRepository()


# For future enhancement: Add database session management
# def get_db_session() -> Generator:
#     """Get database session with proper cleanup."""
#     try:
#         # Create session
#         session = SessionLocal()
#         yield session
#     finally:
#         session.close() 