from datetime import datetime
from bson import ObjectId
from typing import Dict, Any, Optional

class ImageFeedback:
    """
    Model representing user feedback on an image description.
    """
    def __init__(
        self,
        user_id: ObjectId,
        image_id: ObjectId,
        user_transcription: str,
        better_version: str,
        explanation: str,
        _id: Optional[ObjectId] = None,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or ObjectId()
        self.user_id = user_id
        self.image_id = image_id
        self.user_transcription = user_transcription
        self.better_version = better_version
        self.explanation = explanation
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the ImageFeedback instance to a dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "image_id": self.image_id,
            "user_transcription": self.user_transcription,
            "better_version": self.better_version,
            "explanation": self.explanation,
            "created_at": self.created_at,
        } 