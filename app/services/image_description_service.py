import logging
import os
import json
from pathlib import Path
from fastapi import Depends, HTTPException

from app.services.ai_service import AIService
from app.repositories.image_description_repository import ImageDescriptionRepository
from app.repositories.image_feedback_repository import ImageFeedbackRepository
from app.utils.image_description import get_image_description as generate_desc
from app.schemas.image_description import ImageFeedbackRequest

logger = logging.getLogger(__name__)
IMAGES_DIR = Path(__file__).parent.parent / "uploads" / "images"

class ImageDescriptionService:
    def __init__(
        self,
        ai_service: AIService = Depends(),
        image_desc_repo: ImageDescriptionRepository = Depends(),
        image_feedback_repo: ImageFeedbackRepository = Depends(),
    ):
        self.ai_service = ai_service
        self.image_desc_repo = image_desc_repo
        self.image_feedback_repo = image_feedback_repo

    def get_practice_images(self) -> list:
        try:
            image_files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if not image_files:
                return []

            all_images = self.image_desc_repo.find_all()
            saved_image_dict = {img["name"]: img for img in all_images}

            for image_file in image_files:
                image_url = f"/uploads/images/{image_file}"
                if image_url not in saved_image_dict:
                    img_path = str(IMAGES_DIR / image_file)
                    detail_description = generate_desc(img_path)
                    
                    new_image_data = {
                        "name": image_url,
                        "file_path": img_path,
                        "detail_description": detail_description
                    }
                    self.image_desc_repo.create(new_image_data)
            
            return self.image_desc_repo.find_all()

        except Exception as e:
            logger.error(f"Error getting practice images: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Could not retrieve practice images.")

    def get_image_path_by_id(self, image_id: str) -> Path:
        image_doc = self.image_desc_repo.find_by_id(image_id)
        if not image_doc or 'file_path' not in image_doc:
            raise HTTPException(status_code=404, detail="Image not found")
        
        image_path = Path(image_doc['file_path'])
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image file not found on server")
            
        return image_path

    def provide_image_feedback(self, feedback_request: ImageFeedbackRequest) -> dict:
        try:
            image_data = self.image_desc_repo.find_by_id(feedback_request.image_id)
            if not image_data:
                raise HTTPException(status_code=404, detail="Image not found")

            detail_description = image_data.get('detail_description', 'No description available')
            
            prompt = f"""Detail description of image: '{detail_description}'.
User description: '{feedback_request.user_transcription}'.

Based on the 'Detail description of image' (which serves as a correct and comprehensive reference) and the 'User description' provided above, your task is to analyze the user description and then generate a JSON object as a string.
better_version will be the improved version of the user description that is grammatically correct, coherent, and more descriptive.
explanation will be a brief explanation of the changes made to the user description, highlighting the improvements and clarifications.
This JSON object must have the following exact structure:

{{
"better_version": "<generated_description>",
"explanation": "<generated_explanation>"
}}
"""
            try:
                ai_response = self.ai_service.generate_ai_response_in_json_format(prompt)
                data = json.loads(ai_response)
                better_version = data.get("better_version", "Could not generate improved version")
                explanation = data.get("explanation", "There was an error processing the feedback")
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Error processing AI response for image feedback: {e}")
                better_version = "Could not generate improved version"
                explanation = "There was an error processing the feedback"

            feedback_to_save = {
                "user_id": feedback_request.user_id,
                "image_id": feedback_request.image_id,
                "user_transcription": feedback_request.user_transcription,
                "better_version": better_version,
                "explanation": explanation,
            }
            self.image_feedback_repo.create(feedback_to_save)

            return {"better_version": better_version, "explanation": explanation}

        except Exception as e:
            logger.error(f"Error providing image feedback: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Could not process feedback.") 