from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from bson import ObjectId
from typing import List, Optional
import logging
from datetime import datetime

from app.config.database import db
from app.schemas.conversation import ConversationCreate, ConversationResponse
from app.models.conversation import Conversation
from app.utils.auth import get_current_user
from app.services.ai_service import AIService
from app.services.conversation_service import ConversationService
import json

# Set up logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# =======================
# CONVERSATION ENDPOINTS
# =======================

@router.post("/conversations", response_model=dict)
async def create_conversation(convo_data: ConversationCreate, current_user: dict = Depends(get_current_user)):
    """
    Create a new conversation and generate an initial AI response.
    
    Args:
        convo_data (ConversationCreate): Conversation creation data containing user_role, ai_role, and situation.
        current_user (dict): The authenticated user's information.
        
    Returns:
        dict: A dictionary containing the conversation and initial message.
            
    Raises:
        HTTPException: If there are any errors during conversation creation.
    """
    # Initialize services
    ai_service = AIService()
    conversation_service = ConversationService()
    
    # Get user ID from the current_user dictionary
    user_id = current_user.get("_id")
    if not user_id:
        raise HTTPException(status_code=500, detail="User ID not found in token")
    
    # Validate conversation data
    conversation_service.validate_conversation_data(convo_data)
    
    # Use AI service to refine conversation context
    refined_context = ai_service.refine_conversation_context(
        user_role=convo_data.user_role,
        ai_role=convo_data.ai_role,
        situation=convo_data.situation
    )
    
    # Use conversation service to create conversation
    result = conversation_service.create_conversation(
        user_id=user_id,
        refined_context=refined_context
    )
    
    return result


# GET /conversations - List user conversations (to be implemented)
# This endpoint will retrieve all conversations for the authenticated user

# GET /conversations/{conversation_id} - Get conversation details (to be implemented)  
# This endpoint will retrieve a specific conversation with its metadata

# PUT /conversations/{conversation_id} - Update conversation (to be implemented)
# This endpoint will allow updating conversation settings or metadata

# DELETE /conversations/{conversation_id} - Delete conversation (to be implemented)
# This endpoint will handle conversation deletion and cleanup 