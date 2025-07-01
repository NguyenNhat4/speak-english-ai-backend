from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from bson import ObjectId

class MessageCreate(BaseModel):
    content: str
    audio_path: Optional[str] = None
    transcription: Optional[str] = None
    feedback_id: Optional[str] = None

class MessageResponse(BaseModel):
    id: str = Field(alias="_id")
    conversation_id: str
    sender: str
    content: str
    timestamp: datetime
    audio_path: Optional[str] = None
    transcription: Optional[str] = None
    feedback_id: Optional[str] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: lambda v: str(v)
        }

    @validator("id", "conversation_id", "feedback_id", pre=True)
    def convert_objectid_to_str(cls, v):
        if v and isinstance(v, ObjectId):
            return str(v)
        return v

class UserAndAIResponse(BaseModel):
    user_message: MessageResponse
    ai_message: MessageResponse
        
