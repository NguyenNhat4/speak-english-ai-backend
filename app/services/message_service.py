import logging
from fastapi import Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional

from app.services.conversation_service import ConversationService
from app.services.feedback_service import FeedbackService
from app.services.ai_service import AIService
from app.repositories.message_repository import MessageRepository
from app.repositories.audio_repository import AudioRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.message import MessageResponse
from app.utils.object_id import mongo_doc_to_schema

logger = logging.getLogger(__name__)

class MessageService:
    def __init__(
        self,
        conversation_service: Optional[ConversationService] = None,
        feedback_service: Optional[FeedbackService] = None,
        ai_service: Optional[AIService] = None,
        message_repo: Optional[MessageRepository] = None,
        audio_repo: Optional[AudioRepository] = None,
        feedback_repo: Optional[FeedbackRepository] = None,
    ):
        self.conversation_service = conversation_service or ConversationService()
        self.feedback_service = feedback_service or FeedbackService()
        self.ai_service = ai_service or AIService()
        self.message_repo = message_repo or MessageRepository()
        self.audio_repo = audio_repo or AudioRepository()
        self.feedback_repo = feedback_repo or FeedbackRepository()

    async def process_user_message(
        self,
        conversation_id: str,
        audio_id: str,
        user_id: str,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        
        conversation_context = self.conversation_service.get_conversation_context(conversation_id)
        conversation = conversation_context["conversation"]

        if str(conversation["user_id"]) != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this conversation")

        audio_data = self.audio_repo.find_by_id(audio_id)
        if not audio_data:
            raise HTTPException(status_code=404, detail="Audio data not found")

        user_message_doc = self.message_repo.create_message(
            conversation_id=conversation_id,
            sender="user",
            content=audio_data["transcription"],
            audio_path=audio_data["file_path"],
            transcription=audio_data["transcription"]
        )

        background_tasks.add_task(
            self.feedback_service.generate_speech_feedback,
            transcription=audio_data["transcription"],
            user_id=user_id,
            conversation_id=conversation_id,
            audio_id=str(audio_data["_id"]),
            file_path=audio_data["file_path"],
            user_message_id=str(user_message_doc['_id'])
        )

        messages = conversation_context["messages"]
        # Add the new user message to the history for the AI prompt
        messages.append(user_message_doc)

        conversation_history_text = "\n".join([f"{msg['sender']}: {msg['content']}" for msg in messages])
        prompt = self.ai_service.build_conversation_prompt(conversation, conversation_history_text)

        ai_text = self.ai_service.generate_ai_response(prompt)

        ai_message_doc = self.message_repo.create_message(
            conversation_id=conversation_id,
            sender="ai",
            content=ai_text
        )

        user_message = mongo_doc_to_schema(user_message_doc, MessageResponse)
        ai_message = mongo_doc_to_schema(ai_message_doc, MessageResponse)

        return {
            "user_message": user_message,
            "ai_message": ai_message
        }

    def get_messages_by_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        return self.message_repo.get_messages_by_conversation(conversation_id)

    def get_message(self, message_id: str) -> Dict[str, Any]:
        message = self.message_repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        return message

    def delete_message(self, message_id: str):
        deleted = self.message_repo.delete(message_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"message": "Message deleted successfully"}

    def get_feedback_for_message(self, message_id: str) -> dict:
        """
        Get user-friendly feedback for a specific message.
        """
        message = self.message_repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        feedback_id = message.get("feedback_id")
        if not feedback_id:
            return {"user_feedback": "Feedback is still being generated. Please try again in a moment.", "is_ready": False}

        feedback = self.feedback_repo.find_by_id(str(feedback_id))
        if not feedback:
            return {"user_feedback": "No feedback available for this message.", "is_ready": False}

        return {
            "user_feedback": {
                "id": str(feedback.get("id")),
                "user_feedback": feedback.get("user_feedback", "Feedback content unavailable"),
                "created_at": feedback.get("created_at")
            },
            "is_ready": True
        } 