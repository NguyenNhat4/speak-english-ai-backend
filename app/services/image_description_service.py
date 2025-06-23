import logging
import os
import json
from pathlib import Path
from fastapi import Depends, HTTPException
import requests

from app.config.settings import settings
from app.utils.ai_utils import generate_ai_response_in_json_format, generate_image_description
from app.repositories.image_description_repository import ImageDescriptionRepository
from app.repositories.image_feedback_repository import ImageFeedbackRepository
from app.schemas.image_description import ImageFeedbackRequest

logger = logging.getLogger(__name__)
IMAGES_DIR = Path(__file__).parent.parent / "uploads" / "images"

class ImageDescriptionService:
    def __init__(
        self,
        image_desc_repo: ImageDescriptionRepository = Depends(),
        image_feedback_repo: ImageFeedbackRepository = Depends(),
    ):
        self.image_desc_repo = image_desc_repo
        self.image_feedback_repo = image_feedback_repo
        self.description_prompt = """ Generate a concise and objective description of the provided image, 
suitable for a TOEIC picture description test. The description should be spoken aloud 
in approximately 30-45 seconds. Focus on the following elements in this order: 
1. Overall Scene/Main Idea: Begin with a single sentence summarizing what is generally 
happening or what the image primarily depicts. 2. People: State the number of people 
visible. Describe their main actions or activities. Briefly mention their attire if
it's distinctive or relevant. If facial expressions are clear and unambiguous, briefly 
note them (e.g., "smiling," "concentrating"). Avoid guessing emotions. 
3. Key Objects and Setting: Identify prominent objects in the foreground 
and background. Describe their locations relative to each other or the people.
Clearly state whether the setting is indoors or outdoors, and specify the type 
of location if obvious (e.g., office, park, kitchen, street). 
4. Concluding Observation (Optional and Brief): If there's a very clear and
objective overall impression or atmosphere 
(e.g., "It appears to be a busy workday," "The scene looks like a casual gathering"),
you can mention it briefly. Avoid subjective interpretations or storytelling. 
Important Considerations for the AI: Use clear and precise vocabulary. 
Maintain a neutral and objective tone. Focus on what is directly visible 
in the image. Do not make assumptions or inferences beyond what is clearly 
shown. Structure the description logically. Ensure grammatical accuracy and
fluency. The output should be a direct description, not a story or interpretation
"""

    def _download_images_from_links(self):
        """
        Downloads images from a list of URLs in image_link.txt.
        """
        output_dir = IMAGES_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        link_file = Path(__file__).parent.parent / 'utils' / 'image_link.txt'
        if not link_file.exists():
            logger.warning(f"Image link file not found at: {link_file}")
            return
            
        with open(link_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('# ')]
        
        for url in urls:
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    filename = url.split('/')[-1]
                    filepath = output_dir / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"Successfully downloaded: {filename}")
                else:
                    logger.warning(f"Failed to download: {url} with status {response.status_code}")
            except Exception as e:
                logger.error(f"Error downloading {url}: {str(e)}")

    def get_practice_images(self) -> list:
        try:
            # Ensure the images directory exists before trying to list its contents
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            
            if not os.listdir(IMAGES_DIR):
                self._download_images_from_links()

            image_files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if not image_files:
                return []

            all_images = self.image_desc_repo.find_all()
            saved_image_dict = {img["name"]: img for img in all_images}

            for image_file in image_files:
                image_url = f"/uploads/images/{image_file}"
                if image_url not in saved_image_dict:
                    img_path = str(IMAGES_DIR / image_file)
                    detail_description = generate_image_description(img_path, self.description_prompt)
                    
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
                ai_response = generate_ai_response_in_json_format(prompt)
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