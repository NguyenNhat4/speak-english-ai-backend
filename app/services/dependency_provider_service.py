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
from app.utils.auth import oauth2_scheme
from fastapi import Depends
from fastapi.security import SecurityScopes
from typing import Dict, Any
# Import the provider to resolve the self reference issue
from app.services import provider

class DependencyProviderService:
    def get_audio_repository(self) -> AudioRepository:
        return AudioRepository()

    def get_conversation_repository(self) -> ConversationRepository:
        return ConversationRepository()

    def get_feedback_repository(self) -> FeedbackRepository:
        return FeedbackRepository()
    
    def get_message_repository(self) -> MessageRepository:
        return MessageRepository()

    def get_user_repository(self) -> UserRepository:
        return UserRepository()
        
    def get_image_description_repository(self) -> ImageDescriptionRepository:
        return ImageDescriptionRepository()

    def get_image_feedback_repository(self) -> ImageFeedbackRepository:
        return ImageFeedbackRepository()

    def get_user_service(self) -> UserService:
        return UserService(user_repo=self.get_user_repository())

    def get_audio_service(self) -> AudioService:
        return AudioService(audio_repo=self.get_audio_repository())

    def get_conversation_service(self) -> ConversationService:
        return ConversationService(
            conversation_repo=self.get_conversation_repository(),
            message_repo=self.get_message_repository()
        )

    def get_ai_service(self) -> AIService:
        return AIService()

    def get_message_service(self) -> MessageService:
        return MessageService(
            message_repo=self.get_message_repository(),
            feedback_repo=self.get_feedback_repository()
        )
    
    def get_tts_service(self) -> TTSService:
        return TTSService(
            message_repo=self.get_message_repository(),
            conversation_repo=self.get_conversation_repository()
        )
        
    def get_image_description_service(self) -> ImageDescriptionService:
        return ImageDescriptionService(
            image_desc_repo=self.get_image_description_repository(),
            image_feedback_repo=self.get_image_feedback_repository()
        )

    def get_orchestration_service(self) -> OrchestrationService:
        return OrchestrationService(
            conversation_service=self.get_conversation_service(),
            ai_service=self.get_ai_service(),
            audio_repo=self.get_audio_repository(),
            message_repo=self.get_message_repository(),
            feedback_repo=self.get_feedback_repository()
        )

    def get_current_active_user(
        self,
        security_scopes: SecurityScopes,
        token: str = Depends(oauth2_scheme),
        user_service: UserService = Depends(provider.get_user_service)
    ) -> Dict[str, Any]:
        return user_service.get_user_from_token(token, security_scopes.scopes)

    def get_current_admin_user(
        self,
        security_scopes: SecurityScopes,
        token: str = Depends(oauth2_scheme),
        user_service: UserService = Depends(provider.get_user_service)
    ) -> Dict[str, Any]:
        # Enforce "admin" scope
        if "admin" not in security_scopes.scopes:
            security_scopes.scopes.append("admin")
        return user_service.get_user_from_token(token, security_scopes.scopes) 