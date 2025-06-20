from app.repositories.base_repository import BaseRepository
from app.models.image_feedback import ImageFeedback

class ImageFeedbackRepository(BaseRepository[ImageFeedback]):
    """
    Repository for image feedback data.
    """
    def __init__(self):
        super().__init__("image_feedbacks", ImageFeedback) 