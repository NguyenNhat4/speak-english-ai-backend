import logging
from fastapi import Depends, HTTPException
from typing import Dict, Any, List, Optional

from app.repositories.message_repository import MessageRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.message import MessageResponse
from app.schemas.feedback import MessageFeedbackResponse, MessageFeedbackContent
from app.utils.object_id import mongo_doc_to_schema

logger = logging.getLogger(__name__)

class MessageService:
    def __init__(
        self,
        message_repo: Optional[MessageRepository] = None,
        feedback_repo: Optional[FeedbackRepository] = None,
    ):
        self.message_repo = message_repo or MessageRepository()
        self.feedback_repo = feedback_repo or FeedbackRepository()

    def get_messages_by_conversation(self, conversation_id: str) -> List[MessageResponse]:
        messages_data = self.message_repo.get_messages_by_conversation(conversation_id)
        return [MessageResponse.model_validate(msg) for msg in messages_data]

    def get_message(self, message_id: str) -> MessageResponse:
        message = self.message_repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        return MessageResponse.model_validate(message)

    def delete_message(self, message_id: str):
        deleted = self.message_repo.delete(message_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"message": "Message deleted successfully"}

    def get_feedback_for_message(self, message_id: str) -> MessageFeedbackResponse:
        """
        Get user-friendly feedback for a specific message.
        """
        message = self.message_repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        feedback_id = message.get("feedback_id")
        if not feedback_id:
            return MessageFeedbackResponse(
                user_feedback=None,
                is_ready=False
            )

        feedback = self.feedback_repo.find_by_id(str(feedback_id))
        if not feedback:
            return MessageFeedbackResponse(
                user_feedback=None,
                is_ready=False
            )

        feedback_content = MessageFeedbackContent.model_validate(feedback)
        return MessageFeedbackResponse(
            user_feedback=feedback_content,
            is_ready=True
        ) 