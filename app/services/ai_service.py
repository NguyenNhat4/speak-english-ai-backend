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

from app.utils.gemini import generate_response
from app.utils.tts_client_service import pick_suitable_voice_name
from app.models.results.feedback_result import FeedbackResult

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Data class for conversation context used in AI interactions."""
    user_role: str = "Student"
    ai_role: str = "Teacher"
    situation: str = "General conversation"
    previous_exchanges: str = ""


class AIServiceError(Exception):
    """Custom exception for AI service errors."""
    pass


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
    
    def refine_conversation_context(
        self, 
        user_role: str, 
        ai_role: str, 
        situation: str
    ) -> Dict[str, Any]:
        """
        Refine conversation context using AI to create coherent scenarios.
        
        Args:
            user_role: The role of the user in the conversation
            ai_role: The role of the AI in the conversation  
            situation: The conversation situation/context
            
        Returns:
            Dict containing refined conversation context with all required fields
            
        Raises:
            HTTPException: If AI response processing fails
        """
        try:
            prompt = self._build_refinement_prompt_init_conversation(user_role, ai_role, situation)
            cleaned_response = self.generate_ai_response_in_json_format(prompt)
            
            # Parse and validate the response
            data_json = json.loads(cleaned_response)
            self._validate_refinement_response(data_json)
            
            # Pick suitable voice based on AI gender
            voice_type = pick_suitable_voice_name(data_json["ai_gender"])
            data_json["voice_type"] = voice_type
            
            self.logger.info(f"Successfully refined conversation context for roles: {user_role} -> {ai_role}")
            return data_json
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}\nResponse text: {cleaned_response}")
            raise HTTPException(
                status_code=500,
                detail="Failed to process AI response format"
            )
        except ValueError as e:
            self.logger.error(f"Invalid response format: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )
        except Exception as e:
            self.logger.error(f"Unexpected error processing AI response: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred while processing the AI response"
            )
    
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
            response = generate_response(prompt)
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

    def generate_ai_response_in_json_format(self, prompt: str) -> str:
        """
        Generate an AI response and clean JSON formatting markers.
        
        Args:
            prompt: The prompt for generating the AI response
            
        Returns:
            The cleaned JSON response
            
        Raises:
            HTTPException: If AI response generation fails
        """
        try:
            response = generate_response(prompt)
            if not response or not response.strip():
                raise AIServiceError("Empty response from AI service")
                
            # Clean JSON formatting markers
            cleaned_response = self._clean_json_response(response)
                
            self.logger.debug(f"Generated AI JSON response with length: {len(cleaned_response)}")
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
            response = generate_response(prompt)
            
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
    
    def build_conversation_prompt(
        self,
        conversation_context: Dict[str, Any],
        conversation_history: str
    ) -> str:
        """
        Build a conversation prompt for AI response generation.
        
        Args:
            conversation_context: Dictionary containing conversation details
            conversation_history: Formatted conversation history
            
        Returns:
            Formatted prompt for conversation AI
        """
        prompt = (
            f"You are playing the role of {conversation_context['ai_role']} and the user is {conversation_context['user_role']}. "
            f"The situation is: {conversation_context['situation']}. "
            f"Stay fully in character as {conversation_context['ai_role']}. "
            f"Use natural, simple English that new and intermediate learners can easily understand. "
            f"Keep your response short and literally alike the role you are in (1 to 4 sentences). "
            f"Avoid special characters like brackets or symbols. "
            f"Do not refer to the user with any placeholder like a name in brackets. Don't include asterisk in your response. "
            f"Ask an open-ended question that fits the situation and encourages the user to speak more."
            f"\nHere is the conversation so far:\n{conversation_history}"
            f"\nNow respond as {conversation_context['ai_role']}."
        )
        
        return prompt
    
    def _validate_feedback_input(self, transcription: str) -> None:
        """Validate feedback generation input."""
        if not transcription or not transcription.strip():
            raise AIServiceError("Transcription cannot be empty")
        
        if len(transcription) > 5000:  # Reasonable limit
            raise AIServiceError("Transcription too long for feedback generation")
    
    def _clean_json_response(self, response: str) -> str:
        """Clean JSON response formatting."""
        cleaned_response = response.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:].lstrip('\n')
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3].rstrip('\n')
        return cleaned_response
    
    def _clean_feedback_response(self, response: str) -> str:
        """Clean and format feedback response."""
        cleaned_text = response.strip()
        
        # Remove common markdown formatting
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        
        return cleaned_text.strip()
    
    def _build_feedback_prompt(
        self, 
        transcription: str, 
        context: ConversationContext
    ) -> str:
        """
        Build optimized prompt for generating user feedback.
        
        Args:
            transcription: Transcribed text from the user's speech
            context: Conversation context information
            
        Returns:
            Formatted prompt string for AI feedback generation
        """
        # Build context section
        context_section = f"""
Context:
- User role: {context.user_role}
- AI role: {context.ai_role}
- Situation: {context.situation}

Previous exchanges:
\"\"\"{context.previous_exchanges or 'No previous exchanges'}\"\"\""""
        
        # Build main feedback prompt
        prompt = f"""
{context_section}

Current student's speech: "{transcription}"

You are an expert English teacher providing feedback on a student's speech. This feedback will be shown when the user clicks the feedback button. Do not greet the user or add extra commentary.

Note: The user's speech is transcribed from audio and may lack punctuation. Do not comment on missing punctuation.

Generate feedback in Vietnamese following this structure:
1. Phân tích câu trả lời của người học và chỉ ra các lỗi về ngữ pháp và từ vựng
2. Cung cấp gợi ý hoặc ví dụ về cách dùng từ/cụm từ tốt hơn để diễn đạt tự nhiên hơn
3. Đưa ra 2-3 phiên bản câu hoàn chỉnh hơn, sát với câu gốc nhưng đúng hơn, phù hợp với trình độ người học
4. Phân tích cấu trúc ngữ pháp (mental model) của câu ví dụ: chỉ ra chủ ngữ, động từ, bổ ngữ, cách dùng mệnh đề phụ (nếu có), và chức năng giao tiếp của từng phần trong câu (so sánh với câu gốc)
5. Nếu câu trả lời ngắn, chưa rõ ý, hoặc sai lệch hoàn toàn, đưa ra câu trả lời mẫu đơn giản hơn phù hợp với trình độ hiện tại

Return only the feedback content in Vietnamese.
"""
        
        return prompt.strip()

    def _build_refinement_prompt_init_conversation(
        self, 
        user_role: str, 
        ai_role: str, 
        situation: str
    ) -> str:
        """
        Build the prompt for refining roles and situation.
        
        Args:
            user_role: The user's role
            ai_role: The AI's role
            situation: The conversation situation
            
        Returns:
            The formatted prompt for AI refinement
        """
        return f"""
        You are an AI assistant designed to engage in role-playing scenarios to help new, intermediate English learners in a natural, real-life conversation. 
        You will be provided with a user role, an AI role, and a situation. These inputs may be incomplete, vague, or inconsistent. Your task is to:

        Analyze the given user role, AI role, and situation.

        Refine them to create a coherent and logical scenario. This may involve:
    
        Adjusting roles or situations that don't make sense together (e.g., if the roles and situation are incompatible, modify them to align).

        Making assumptions where necessary to create a plausible context.

        Use word choice that matches new and intermediate levels, which means it's common and close to real-life.

        User role and AI role: 1-2 words. 

        Once you have a refined scenario, generate an appropriate initial response as the AI in that scenario.

        Return the refined roles, situation, and response as a JSON object.

        Return your output in the following JSON format:
        {{
        "refined_user_role": "[your refined user role]",
        "refined_ai_role": "[your refined AI role]",
        "refined_situation": "[your refined situation]",
        "response": "[your first  response as refined_ai_role to the user regardless of the situation  you can use a random name for the user and yourself]"
        "ai_gender": "[decide female or male base on the refined_ai_role,refined_situation ]" ]"
        }}

        Here are the inputs:
        User role: {user_role}
        AI role:  {ai_role}
        Situation: {situation}
        """
    
    def _validate_refinement_response(self, data_json: Dict[str, Any]) -> None:
        """
        Validate the AI refinement response contains all required fields.
        
        Args:
            data_json: The parsed JSON response to validate
            
        Raises:
            ValueError: If required fields are missing
        """
        required_fields = [
            "refined_user_role", 
            "refined_ai_role", 
            "refined_situation", 
            "response",
            "ai_gender"
        ]
        
        missing_fields = [field for field in required_fields if field not in data_json]
        if missing_fields:
            raise ValueError(f"Missing required fields in AI response: {', '.join(missing_fields)}")
        
        # Validate non-empty values
        empty_fields = [field for field in required_fields if not data_json[field].strip()]
        if empty_fields:
            raise ValueError(f"Empty values for required fields: {', '.join(empty_fields)}") 