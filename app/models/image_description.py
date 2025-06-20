from datetime import datetime
from bson import ObjectId
from typing import Dict, Any, Optional

class ImageDescription:
    """
    Model representing a practice image and its description.
    """
    def __init__(
        self,
        name: str, # URL of the image
        file_path: str,
        detail_description: str,
        user_id: Optional[ObjectId] = None, # User who uploaded, if any
        _id: Optional[ObjectId] = None,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or ObjectId()
        self.name = name
        self.file_path = file_path
        self.detail_description = detail_description
        self.user_id = user_id
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the ImageDescription instance to a dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "name": self.name,
            "file_path": self.file_path,
            "detail_description": self.detail_description,
            "user_id": self.user_id,
            "created_at": self.created_at,
        } 