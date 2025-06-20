from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from typing import List

from app.services.image_description_service import ImageDescriptionService
from app.schemas.image_description import ImageDescriptionResponse, ImageFeedbackRequest, ImageFeedbackResponse
from app.utils.auth import get_current_user
from app.utils.dependencies import get_image_description_service

router = APIRouter(
    prefix="/images",
    tags=["images"]
)

@router.get("/practice", response_model=List[ImageDescriptionResponse])
def get_practice_images(
    service: ImageDescriptionService = Depends(get_image_description_service)
):
    """
    Returns a list of practice images with IDs and URLs.
    If new images are found in the directory, they are processed and added.
    """
    return service.get_practice_images()

@router.get("/{image_id}/file", response_class=FileResponse)
def get_image_file(
    image_id: str,
    service: ImageDescriptionService = Depends(get_image_description_service)
):
    """
    Returns the actual image file by its ID.
    """
    image_path = service.get_image_path_by_id(image_id)
    return FileResponse(image_path)

@router.post("/feedback", response_model=ImageFeedbackResponse)
def provide_feedback(
    feedback_request: ImageFeedbackRequest,
    service: ImageDescriptionService = Depends(get_image_description_service),
    current_user: dict = Depends(get_current_user) # Ensure user is authenticated
):
    """
    Accepts user feedback on an image description and returns an improved version.
    """
    # Note: feedback_request already contains user_id. We could validate it against current_user.
    return service.provide_image_feedback(feedback_request)





