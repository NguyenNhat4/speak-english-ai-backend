"""
Services module for SpeakAI application.

This module contains all business logic services that handle
specific domains of the application functionality.
"""

from .audio_service import AudioService
from .ai_service import AIService
from .conversation_service import ConversationService
from .user_service import UserService
from .message_service import MessageService
from .tts_service import TTSService
from .image_description_service import ImageDescriptionService
from .orchestration_service import OrchestrationService
from .feedback_service import FeedbackService
from .dependency_provider_service import DependencyProviderService

__all__ = [
    "AIService",
    "ConversationService",
    "UserService",
    "MessageService",
    "AudioService",
    "TTSService",
    "FeedbackService",
    "DependencyProviderService"
]

# All methods are now static, so we export the class directly
provider = DependencyProviderService
