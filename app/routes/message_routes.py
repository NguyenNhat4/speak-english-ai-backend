from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from typing import List, Dict, Any

from app.schemas.message import MessageResponse
from app.utils.auth import get_current_user
from app.services.message_service import MessageService
from app.utils.dependencies import get_message_service

router = APIRouter(
    tags=["messages"]
)

@router.post("/conversations/{conversation_id}/messages", response_model=Dict[str, Any])
async def add_message_and_get_response(
    conversation_id: str,
    audio_id: str,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    message_service: MessageService = Depends(get_message_service)
):
    """
    Process a user's spoken message, add it to the conversation, and get an AI response.
    Triggers feedback generation in the background.
    """
    user_id = str(current_user["_id"])
    return await message_service.process_user_message(
        conversation_id, audio_id, user_id, background_tasks
    )

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conversation_id: str,
    message_service: MessageService = Depends(get_message_service)
):
    """
    Get all messages for a specific conversation.
    """
    return message_service.get_messages_by_conversation(conversation_id)

@router.get("/messages/{message_id}", response_model=MessageResponse)
def get_message(
    message_id: str,
    message_service: MessageService = Depends(get_message_service)
):
    """
    Get a specific message by its ID.
    """
    return message_service.get_message(message_id)

@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    message_id: str,
    message_service: MessageService = Depends(get_message_service)
):
    """
    Delete a message.
    """
    message_service.delete_message(message_id)
    return None

@router.get("/messages/{message_id}/feedback", response_model=dict)
def get_message_feedback(
    message_id: str,
    message_service: MessageService = Depends(get_message_service)
):
    """
    Get user-friendly feedback for a specific message.
    """
    return message_service.get_feedback_for_message(message_id)

# GET /messages/{message_id} - Get message details (to be implemented)
# This endpoint will retrieve a specific message with its content and metadata

# PUT /messages/{message_id} - Update message (to be implemented)
# This endpoint will allow updating message content or metadata

# DELETE /messages/{message_id} - Delete message (to be implemented)
# This endpoint will handle message deletion

# GET /conversations/{conversation_id}/messages - List conversation messages (to be implemented)
# This endpoint will retrieve all messages for a specific conversation 