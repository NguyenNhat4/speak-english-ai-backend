from fastapi import APIRouter, Depends, status, Security
from typing import List, Dict, Any

from app.schemas.conversation import ConversationCreate, ConversationResponse, ConversationUpdate
from app.schemas.user import UserResponse
from app.services import provider
from app.services.conversation_service import ConversationService

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"]
)

@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_conversation(
    convo_data: ConversationCreate, 
    current_user: UserResponse = Security(provider.get_current_active_user, scopes=["user"]),
    conversation_service: ConversationService = Depends(provider.get_conversation_service)
):
    """
    Create a new conversation and generate an initial AI response.
    """
    user_id = str(current_user.id)
    return conversation_service.create_new_conversation(user_id, convo_data)

@router.get("", response_model=List[ConversationResponse])
def get_user_conversations(
    current_user: UserResponse = Security(provider.get_current_active_user, scopes=["user"]),
    conversation_service: ConversationService = Depends(provider.get_conversation_service)
):
    """
    Get all conversations for the current user.
    """
    user_id = str(current_user.id)
    return conversation_service.get_user_conversations(user_id)

@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    conversation_service: ConversationService = Depends(provider.get_conversation_service)
):
    """
    Get a specific conversation by its ID.
    """
    return conversation_service.get_conversation_by_id(conversation_id)

@router.put("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: str,
    update_data: ConversationUpdate,
    conversation_service: ConversationService = Depends(provider.get_conversation_service)
):
    """
    Update a conversation's metadata.
    """
    return conversation_service.update_conversation(conversation_id, update_data)

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    conversation_service: ConversationService = Depends(provider.get_conversation_service)
):
    """
    Delete a conversation.
    """
    conversation_service.delete_conversation(conversation_id)
    return None 