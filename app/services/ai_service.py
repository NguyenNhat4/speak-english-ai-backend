"""
AI Service for handling all AI-related business logic.

This service manages AI interactions, prompt building, and response processing
for the SpeakAI application. This includes conversation responses, feedback generation,
and any other AI-powered features.
"""

import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from fastapi import HTTPException

from app.config.settings import settings
from app.models.results.feedback_result import FeedbackResult
from app.utils.ai_utils import get_gemini_model, _generate_response, AIServiceError

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Data class for conversation context used in AI interactions."""
    user_role: str = "Student"
    ai_role: str = "Teacher"
    situation: str = "General conversation"
    previous_exchanges: str = ""


class AIService:
    """
    Service class for handling all AI interactions and prompt processing.
    
    This service encapsulates all AI-related business logic including:
    - Conversation response generation
    - Feedback generation for language learning
    - Prompt building and optimization
    - Response processing and validation
    """
    
    def __init__(self):
        """Initialize the AI service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.gemini_model = get_gemini_model()

    def generate_ai_response(self, prompt: str) -> str:
        """
        Generate a plain text AI response for conversational purposes.
        
        Args:
            prompt: The prompt for generating the AI response
            
        Returns:
            The plain text AI response
            
        Raises:
            HTTPException: If AI response generation fails
        """
        try:
            response = _generate_response(prompt)
            if not response or not response.strip():
                raise AIServiceError("Empty response from AI service")
                
            # For plain text responses, just strip whitespace
            cleaned_response = response.strip()
            
            self.logger.debug(f"Generated AI response with length: {len(cleaned_response)}")
            return cleaned_response
        
        except AIServiceError as e:
            self.logger.error(f"AI service error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            self.logger.error(f"Failed to generate AI response: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="AI response generation failed"
            )

    def generate_feedback(
        self, 
        transcription: str, 
        context: ConversationContext
    ) -> FeedbackResult:
        """
        Generate user-friendly feedback for speech using AI.
        
        Args:
            transcription: Transcribed text from the user's speech
            context: Conversation context information
            
        Returns:
            FeedbackResult containing user_feedback
            
        Raises:
            AIServiceError: If feedback generation fails
        """
        try:
            self._validate_feedback_input(transcription)
            
            prompt = self._build_feedback_prompt(transcription, context)
            
            # Generate AI feedback
            response = _generate_response(prompt)
            
            if not response or not response.strip():
                raise AIServiceError("Empty feedback response from AI")
            
            # Clean and process the response
            cleaned_feedback = self._clean_feedback_response(response)
            
            self.logger.info(f"Successfully generated feedback for transcription: {transcription[:50]}...")
            return FeedbackResult(user_feedback=cleaned_feedback)
                
        except AIServiceError:
            raise  # Re-raise AI service errors
        except Exception as e:
            self.logger.error(f"Error generating feedback with AI: {e}")
            raise AIServiceError(f"Feedback generation failed: {e}")
    
    def generate_fallback_feedback(self, transcription: str) -> FeedbackResult:
        """
        Generate fallback feedback when AI generation fails.
        
        Args:
            transcription: Transcribed text from user's speech
            
        Returns:
            Basic FeedbackResult with fallback content
        """
        fallback_message = (
            "Cảm ơn bạn đã trả lời. Hiện tại hệ thống không thể phân tích chi tiết câu trả lời của bạn, "
            "nhưng hãy tiếp tục luyện tập. Hãy thử nói chậm và rõ ràng hơn trong lần tiếp theo."
        )
        
        self.logger.info("Generated fallback feedback")
        return FeedbackResult(user_feedback=fallback_message)
    
    def _validate_feedback_input(self, transcription: str) -> None:
        """
        Validate the input for feedback generation.
        """
        if not transcription or not transcription.strip():
            raise AIServiceError("Transcription is required for feedback generation")

    def _clean_feedback_response(self, response: str) -> str:
        """
        Clean the feedback response from the AI model.
        
        This method removes any extraneous formatting, such as markdown,
        and ensures the feedback is presented in a clean, readable format.
        """
        # Basic cleaning: remove markdown and extra whitespace
        # respone include json as well make sure remove the json keyword ```json``` 
        cleaned_response = response.replace("*", "").replace("```", "").strip()
        
        # Further processing can be added here if needed
        
        return cleaned_response
    
    def _build_feedback_prompt(
        self, 
        transcription: str, 
        context: ConversationContext
    ) -> str:
        """
        Build the prompt for generating feedback on user's speech.
        
        This method constructs a detailed prompt for the AI model, including
        the user's transcription, conversation context, and instructions
        for generating helpful feedback.
        """
        # Unpack context for clarity
        user_role = context.user_role
        ai_role = context.ai_role
        situation = context.situation
        previous_exchanges = context.previous_exchanges

        # Construct a detailed, user-friendly prompt
        prompt = f"""
            As a language learning assistant, your task is to provide feedback on the user's response 
            in a given scenario. The feedback should be encouraging, clear, and focused on 
            improving their language skills.

            **Scenario Details:**
            - **Your Role:** {ai_role}
            - **User's Role:** {user_role}
            - **Situation:** {situation}

            **Conversation History:**
            {previous_exchanges}

            **User's Response to Analyze:**
            "{transcription}"

            **Feedback Requirements:**
            1.  **Be Encouraging:** Start with a positive and encouraging sentence.
            2.  **Clarity and Conciseness:** Provide feedback that is easy to understand. 
                Avoid overly technical jargon.
            3.  **Constructive Corrections:** If there are grammatical errors or awkward phrasing, 
                gently correct them and provide a brief explanation.
            4.  **Actionable Advice:** Suggest specific ways the user can improve, such as using 
                different vocabulary or sentence structures.
            5.  **Stay in Character:** If applicable, maintain the persona of your assigned role.

            Please provide the feedback directly, without any additional conversational text
            unless it's part of the feedback itself.
        """
        
        self.logger.debug(f"Built feedback prompt for transcription: {transcription[:30]}...")
        return prompt 