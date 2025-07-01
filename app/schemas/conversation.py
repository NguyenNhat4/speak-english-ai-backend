from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from .message import MessageResponse

class ConversationCreate(BaseModel):
    user_role: str
    ai_role: str
    situation: str
    

class ConversationResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    user_role: str
    ai_role: str
    situation: str
    started_at: datetime
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: lambda v: str(v)
        }

    @validator("id", "user_id", pre=True)
    def convert_objectid_to_str(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v

class ConversationUpdate(BaseModel):
    user_role: Optional[str] = None
    ai_role: Optional[str] = None
    situation: Optional[str] = None
    ended_at: Optional[datetime] = None

class ConversationContext(BaseModel):
    conversation: ConversationResponse
    messages: List[MessageResponse]
    history: List[Dict[str, Any]]
