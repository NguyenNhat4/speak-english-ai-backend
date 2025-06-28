"""
A service dedicated to providing instances of other services and repositories.
This centralizes the dependency injection logic into the service layer,
avoiding direct calls from routes to a utility file.
"""
from app.services.audio_service import AudioService
from app.services.conversation_service import ConversationService
from app.services.ai_service import AIService
from app.services.user_service import UserService
from app.services.message_service import MessageService
from app.services.tts_service import TTSService
from app.services.image_description_service import ImageDescriptionService
from app.services.orchestration_service import OrchestrationService
from app.repositories.audio_repository import AudioRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.repositories.image_description_repository import ImageDescriptionRepository
from app.repositories.image_feedback_repository import ImageFeedbackRepository
from app.schemas.user import UserResponse
from app.utils.auth import oauth2_scheme
from fastapi import Depends
from fastapi.security import SecurityScopes
from typing import Dict, Any

class DependencyProviderService:
    @staticmethod
    def get_audio_repository() -> AudioRepository:
        return AudioRepository()

    @staticmethod
    def get_conversation_repository() -> ConversationRepository:
        return ConversationRepository()

    @staticmethod
    def get_feedback_repository() -> FeedbackRepository:
        return FeedbackRepository()
    
    @staticmethod
    def get_message_repository() -> MessageRepository:
        return MessageRepository()

    @staticmethod
    def get_user_repository() -> UserRepository:
        return UserRepository()
        
    @staticmethod
    def get_image_description_repository() -> ImageDescriptionRepository:
        return ImageDescriptionRepository()

    @staticmethod
    def get_image_feedback_repository() -> ImageFeedbackRepository:
        return ImageFeedbackRepository()

    @staticmethod
    def get_user_service() -> UserService:
        return UserService(user_repo=DependencyProviderService.get_user_repository())

    @staticmethod
    def get_audio_service() -> AudioService:
        return AudioService(audio_repo=DependencyProviderService.get_audio_repository())

    @staticmethod
    def get_conversation_service() -> ConversationService:
        return ConversationService(
            conversation_repo=DependencyProviderService.get_conversation_repository(),
            message_repo=DependencyProviderService.get_message_repository()
        )

    @staticmethod
    def get_ai_service() -> AIService:
        return AIService()

    @staticmethod
    def get_message_service() -> MessageService:
        return MessageService(
            message_repo=DependencyProviderService.get_message_repository(),
            feedback_repo=DependencyProviderService.get_feedback_repository()
        )
    
    @staticmethod
    def get_tts_service() -> TTSService:
        return TTSService(
            message_repo=DependencyProviderService.get_message_repository(),
            conversation_repo=DependencyProviderService.get_conversation_repository()
        )
        
    @staticmethod
    def get_image_description_service() -> ImageDescriptionService:
        return ImageDescriptionService(
            image_desc_repo=DependencyProviderService.get_image_description_repository(),
            image_feedback_repo=DependencyProviderService.get_image_feedback_repository()
        )

    @staticmethod
    def get_orchestration_service() -> OrchestrationService:
        return OrchestrationService(
            conversation_service=DependencyProviderService.get_conversation_service(),
            ai_service=DependencyProviderService.get_ai_service(),
            audio_repo=DependencyProviderService.get_audio_repository(),
            message_repo=DependencyProviderService.get_message_repository(),
            feedback_repo=DependencyProviderService.get_feedback_repository()
        )

    @staticmethod
    def get_current_active_user(
        security_scopes: SecurityScopes,
        token: str = Depends(oauth2_scheme)
    ) -> UserResponse:
        user_repo = UserRepository()
        user_service = UserService(user_repo=user_repo)
        user_data = user_service.get_user_from_token(token, security_scopes.scopes)
        return UserResponse(**user_data)

    @staticmethod
    def get_current_admin_user(
        security_scopes: SecurityScopes,
        token: str = Depends(oauth2_scheme)
    ) -> UserResponse:
        user_repo = UserRepository()
        user_service = UserService(user_repo=user_repo)
        # Enforce "admin" scope
        if "admin" not in security_scopes.scopes:
            security_scopes.scopes.append("admin")
        user_data = user_service.get_user_from_token(token, security_scopes.scopes)
        return UserResponse(**user_data) 