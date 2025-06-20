from app.repositories.base_repository import BaseRepository
from app.models.image_description import ImageDescription

class ImageDescriptionRepository(BaseRepository[ImageDescription]):
    """
    Repository for image description data.
    """
    def __init__(self):
        super().__init__("image_descriptions", ImageDescription)

    def find_by_name(self, name: str):
        return self.find_one({"name": name}) 