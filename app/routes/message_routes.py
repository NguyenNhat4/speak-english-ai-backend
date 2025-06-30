from fastapi import APIRouter, Depends, status, BackgroundTasks, Security
from typing import List, Dict, Any

from app.schemas.message import MessageResponse
from app.schemas.user import UserResponse
from app.services.message_service import MessageService
from app.services.user_service import UserService
from app.services.orchestration_service import OrchestrationService
from app.services.dependency_provider_service import DependencyProviderService

router = APIRouter(
    prefix="/messages",
    tags=["messages"]
)

@router.post("/conversations/{conversation_id}/audio/{audio_id}", response_model=MessageResponse)
async def create_message_from_audio(
    conversation_id: str,
    audio_id: str,
    current_user: UserResponse = Security(DependencyProviderService.get_current_active_user, scopes=["user"]),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    orchestration_service: OrchestrationService = Depends(DependencyProviderService.get_orchestration_service),
):
    """
    Process a user's spoken message, add it to the conversation, and get an AI response.
    Triggers feedback generation in the background.
    """
    user_id = str(current_user.id)
    return await orchestration_service.process_user_message_flow(
        conversation_id, audio_id, user_id, background_tasks
    )

@router.get("/conversations/{conversation_id}", response_model=List[MessageResponse])
def get_conversation_messages(
    conversation_id: str,
    message_service: MessageService = Depends(DependencyProviderService.get_message_service)
):
    """
    Get all messages for a specific conversation.
    """
    return message_service.get_messages_by_conversation(conversation_id)

@router.get("/{message_id}", response_model=MessageResponse)
def get_message(
    message_id: str,
    message_service: MessageService = Depends(DependencyProviderService.get_message_service)
):
    """
    Get a specific message by its ID.
    """
    return message_service.get_message(message_id)

@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    message_id: str,
    message_service: MessageService = Depends(DependencyProviderService.get_message_service)
):
    """
    Delete a message.
    """
    message_service.delete_message(message_id)
    return None

@router.get("/{message_id}/feedback", response_model=dict)
def get_message_feedback(
    message_id: str,
    message_service: MessageService = Depends(DependencyProviderService.get_message_service)
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