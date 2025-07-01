"""
Orchestration Service for handling complex business logic flows
that require coordination between multiple services.
"""
import logging
from fastapi import Depends, HTTPException, BackgroundTasks
from app.services.conversation_service import ConversationService
from app.services.ai_service import AIService, ConversationContext
from app.repositories.audio_repository import AudioRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.message import MessageResponse, UserAndAIResponse
from app.utils.object_id import mongo_doc_to_schema
import app.utils.ai_utils as ai_utils

logger = logging.getLogger(__name__)

class OrchestrationService:
    def __init__(
        self,
        conversation_service: ConversationService,
        ai_service: AIService,
        audio_repo: AudioRepository,
        message_repo: MessageRepository,
        feedback_repo: FeedbackRepository
    ):
        self.conversation_service = conversation_service
        self.ai_service = ai_service
        self.audio_repo = audio_repo
        self.message_repo = message_repo
        self.feedback_repo = feedback_repo

    async def process_user_message_flow(self, conversation_id: str, audio_id: str, user_id: str, background_tasks: BackgroundTasks) -> UserAndAIResponse:
        conversation_context = self.conversation_service.get_conversation_context(conversation_id)
        conversation = conversation_context.conversation

        if conversation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this conversation")

        audio_data = self.audio_repo.find_by_id(audio_id)
        if not audio_data:
            raise HTTPException(status_code=404, detail="Audio data not found")
        
        audio_transcription = audio_data.get("transcription", "")
        audio_filepath = audio_data.get("file_path")

        user_message_doc = self.message_repo.create_message(
            conversation_id=conversation_id,
            sender="user",
            content=audio_transcription,
            audio_path=audio_filepath,
            transcription=audio_transcription
        )

        messages = conversation_context.messages
        # Add the new user message to the history for the AI prompt
        messages.append(MessageResponse.model_validate(user_message_doc))

        conversation_history_text = "\n".join([f"{msg.sender}: {msg.content}" for msg in messages])

        # Generate feedback
        context_for_feedback = ConversationContext(
            user_role=conversation.user_role,
            ai_role=conversation.ai_role,
            situation=conversation.situation,
            previous_exchanges=conversation_history_text
        )
        feedback_result = self.ai_service.generate_feedback(audio_transcription, context_for_feedback)

        # Save feedback
        feedback_to_save = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "audio_id": str(audio_data["_id"]),
            "user_message_id": str(user_message_doc['_id']),
            "user_feedback": feedback_result.user_feedback,
            "target_id": str(user_message_doc['_id']),
            "target_type": "message",
        }
        created_feedback = self.feedback_repo.create(feedback_to_save)
        
        # Link feedback to message
        self.message_repo.update(str(user_message_doc['_id']), {"feedback_id": str(created_feedback['_id'])})
        
        # Generate AI response
        prompt = ai_utils.build_conversation_prompt(conversation, conversation_history_text)
        ai_text = ai_utils.generate_ai_response(prompt)

        ai_message_doc = self.message_repo.create_message(
            conversation_id=conversation_id,
            sender="ai",
            content=ai_text
        )

        user_message = MessageResponse.model_validate(user_message_doc)
        ai_message = MessageResponse.model_validate(ai_message_doc)

        return UserAndAIResponse(
            user_message=user_message,
            ai_message=ai_message
        ) 