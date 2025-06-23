"""
AI-related utility functions.
"""

import json
import logging
from typing import Dict, Any, Optional

from fastapi import HTTPException
import google.generativeai as genai
from PIL import Image

from app.config.settings import settings
from app.utils.voice_utils import pick_suitable_voice_name

logger = logging.getLogger(__name__)

class AIServiceError(Exception):
    """Custom exception for AI service errors."""
    pass

_gemini_model = None

def get_gemini_model():
    """Initializes and returns the Gemini model, caching it for reuse."""
    global _gemini_model
    if _gemini_model is None:
        try:
            logger.info("Initializing Gemini model...")
            genai.configure(api_key=settings.get_gemini_api_key())
            _gemini_model = genai.GenerativeModel(settings.gemini_model_name)
            logger.info("Gemini model initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            raise AIServiceError("Failed to initialize Gemini model") from e
    return _gemini_model

def _generate_response(prompt: str) -> str:
    """
    Generate a response from the Gemini AI model based on the provided prompt.
    """
    model = get_gemini_model()
    response = model.generate_content(prompt)
    return response.text

def _clean_json_response(response: str) -> str:
    """
    Cleans a JSON response string by removing markdown backticks and 'json' prefix.
    """
    return response.strip().replace("```json", "").replace("```", "").strip()

def _validate_refinement_response(data_json: Dict[str, Any]) -> None:
    """
    Validate the structure and content of the refined conversation context response.
    """
    required_keys = ["refined_user_role", "refined_ai_role", "refined_situation", "response", "ai_gender"]
    for key in required_keys:
        if key not in data_json:
            raise ValueError(f"Missing required key in AI response: {key}")

def _build_refinement_prompt_init_conversation(
    user_role: str, 
    ai_role: str, 
    situation: str
) -> str:
    """
    Build the prompt for refining the initial conversation context.
    """
    return f"""
        Please refine the following conversation topic into a more engaging and coherent scenario. 
        Provide the response in JSON format with the following keys:
        - "refined_user_role": A creative and specific version of the user's role.
        - "refined_ai_role": A creative and specific version of the AI's role.
        - "refined_situation": A detailed and engaging scenario for the conversation.
        - "response": A greeting from the AI to the user to start the conversation.
        - "ai_gender": The gender of the AI ("male" or "female").

        Original input:
        - User role: "{user_role}"
        - AI role: "{ai_role}"
        - Situation: "{situation}"
    """

def generate_ai_response_in_json_format(prompt: str) -> str:
    """
    Generate an AI response and clean JSON formatting markers.
    """
    try:
        response = _generate_response(prompt)
        if not response or not response.strip():
            raise AIServiceError("Empty response from AI service")
        
        cleaned_response = _clean_json_response(response)
        
        logger.debug(f"Generated AI JSON response with length: {len(cleaned_response)}")
        return cleaned_response
    
    except AIServiceError as e:
        logger.error(f"AI service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate AI response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="AI response generation failed"
        )

def refine_conversation_context(
    user_role: str, 
    ai_role: str, 
    situation: str
) -> Dict[str, Any]:
    """
    Refine conversation context using AI to create coherent scenarios.
    """
    try:
        prompt = _build_refinement_prompt_init_conversation(user_role, ai_role, situation)
        cleaned_response = generate_ai_response_in_json_format(prompt)
        
        data_json = json.loads(cleaned_response)
        _validate_refinement_response(data_json)
        
        voice_type = pick_suitable_voice_name(data_json["ai_gender"])
        data_json["voice_type"] = voice_type
        
        logger.info(f"Successfully refined conversation context for roles: {user_role} -> {ai_role}")
        return data_json
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}\nResponse text: {cleaned_response}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process AI response format"
        )
    except ValueError as e:
        logger.error(f"Invalid response format: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error processing AI response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the AI response"
        )

def generate_image_description(image_path: str, prompt: str) -> str:
    """
    Generate a description for an image using the Gemini model.

    Args:
        image_path: The path to the image file.
        prompt: The prompt to use for generating the description.

    Returns:
        The generated description as a string.
    """
    if not image_path:
        raise ValueError("Image path must be provided.")
    
    try:
        model = get_gemini_model()
        image = Image.open(image_path)
        
        logger.info(f"Generating description for image: {image_path}")
        response = model.generate_content([prompt, image])
        
        logger.info("Successfully generated image description.")
        return response.text
    except FileNotFoundError:
        logger.error(f"Image file not found at path: {image_path}")
        raise HTTPException(status_code=404, detail=f"Image file not found: {image_path}")
    except Exception as e:
        logger.error(f"Failed to generate image description for {image_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate image description.")

def build_conversation_prompt(conversation: Dict[str, Any], conversation_history: str) -> str:
    """
    Builds the prompt for the conversation given the context and history.
    """
    return f"""
        You are {conversation['ai_role']}.
        The user is {conversation['user_role']}.
        The situation is: {conversation['situation']}.
        Here is the conversation so far:
        {conversation_history}
        AI:
    """

def generate_ai_response(prompt: str) -> str:
    """
    Generates a response from the AI model.
    """
    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        logger.info("Successfully generated AI response for conversation.")
        return response.text
    except Exception as e:
        logger.error(f"Failed to generate conversational AI response: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate AI response.") 