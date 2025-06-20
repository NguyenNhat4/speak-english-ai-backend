from pydantic import BaseModel
from typing import Optional, List

class ImageFeedbackRequest(BaseModel):
    user_id: str
    image_id: str
    user_transcription: str

class ImageFeedbackResponse(BaseModel):
    better_version: Optional[str] = None
    explanation: Optional[str] = None

class ImageDescriptionResponse(BaseModel):
    id: str
    name: str # URL
    detail_description: str

    class Config:
        orm_mode = True 