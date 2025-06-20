import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId

from app.config.database import db
from app.repositories.mistake_repository import MistakeRepository

logger = logging.getLogger(__name__)

class MistakeStatistics:
    """
    Container for mistake statistics as shown in the class diagram.
    """
    def __init__(
        self,
        total_count: int = 0,
        mastered_count: int = 0,
        learning_count: int = 0,
        new_count: int = 0,
        type_distribution: Optional[Dict[str, int]] = None,
        due_for_practice: int = 0,
        mastery_percentage: float = 0.0
    ):
        self.total_count = total_count
        self.mastered_count = mastered_count
        self.learning_count = learning_count
        self.new_count = new_count
        self.type_distribution = type_distribution or {}
        self.due_for_practice = due_for_practice
        self.mastery_percentage = mastery_percentage
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "total_count": self.total_count,
            "mastered_count": self.mastered_count, 
            "learning_count": self.learning_count,
            "new_count": self.new_count,
            "type_distribution": self.type_distribution,
            "due_for_practice": self.due_for_practice,
            "mastery_percentage": self.mastery_percentage
        }

class MistakeService:
    """
    Service for processing, storing, and managing language mistakes.
    
    This service provides functionality to: 
    1. Extract mistakes from feedback
    2. Store unique mistakes in the database
    3. Calculate next practice dates using spaced repetition
    4. Retrieve mistakes for practice
    5. Update mistake status after practice
    """
    
    def __init__(self, mistake_repo: Optional[MistakeRepository] = None):
        """
        Initialize the mistake service with repository dependency.
        
        Args:
            mistake_repo: MistakeRepository instance
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mistake_repo = mistake_repo or MistakeRepository()
    
    def process_feedback_for_mistakes(
        self,
        user_id: str,
        transcription: str,
        feedback: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Extract mistakes from feedback and store them.
        
        Args:
            user_id: ID of the user
            transcription: Original transcription text
            feedback: Feedback data (either raw object or from database)
            context: Optional conversation context
            
        Returns:
            Number of mistakes processed
        """
        try:
            # Handle different feedback structures
            detailed_feedback = {}
            if isinstance(feedback, dict):
                if "detailed_feedback" in feedback:
                    detailed_feedback = feedback.get("detailed_feedback", {})
                else:
                    # Directly using the object as detailed feedback
                    detailed_feedback = feedback
                    
            # Extract grammar mistakes
            grammar_mistakes = []
            for issue in detailed_feedback.get("grammar_issues", []):
                # Only process significant issues (severity > 2)
                if issue.get("severity", 3) > 2:
                    mistake = {
                        "user_id": ObjectId(user_id),
                        "type": "GRAMMAR",
                        "original_text": issue.get("issue", ""),
                        "correction": issue.get("correction", ""),
                        "explanation": issue.get("explanation", ""),
                        "severity": issue.get("severity", 3),
                        "context": self._extract_context(transcription, issue.get("issue", "")),
                        "situation_context": self._extract_situation_context(context),
                        "created_at": datetime.utcnow(),
                        "last_occurred": datetime.utcnow(),
                        "frequency": 1,
                        "last_practiced": None,
                        "practice_count": 0,
                        "success_count": 0,
                        "next_practice_date": self._calculate_next_practice(0, False),
                        "in_drill_queue": True,
                        "is_learned": False,
                        "mastery_level": 0,
                        "status": "NEW"
                    }
                    grammar_mistakes.append(mistake)
            
            # Extract vocabulary mistakes
            vocab_mistakes = []
            for issue in detailed_feedback.get("vocabulary_issues", []):
                mistake = {
                    "user_id": ObjectId(user_id),
                    "type": "VOCABULARY",
                    "original_text": issue.get("original", ""),
                    "correction": issue.get("better_alternative", ""),
                    "explanation": issue.get("reason", ""),
                    "example_usage": issue.get("example_usage", ""),
                    "context": self._extract_context(transcription, issue.get("original", "")),
                    "situation_context": self._extract_situation_context(context),
                    "created_at": datetime.utcnow(),
                    "last_occurred": datetime.utcnow(),
                    "frequency": 1,
                    "last_practiced": None,
                    "practice_count": 0,
                    "success_count": 0,
                    "next_practice_date": self._calculate_next_practice(0, False),
                    "in_drill_queue": True,
                    "is_learned": False,
                    "mastery_level": 0,
                    "status": "NEW"
                }
                vocab_mistakes.append(mistake)
            
            # Combine all mistakes
            all_mistakes = grammar_mistakes + vocab_mistakes
            
            # Store non-duplicate mistakes
            stored_ids = self._store_unique_mistakes(user_id, all_mistakes)
            
            return len(stored_ids)
            
        except Exception as e:
            logger.error(f"Error processing mistakes: {str(e)}")
            raise
    
    def get_unmastered_mistakes(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all unmastered mistakes for a user.
        
        This method matches the class diagram's getUnmasteredMistakes method.
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of unmastered mistakes
        """
        try:
            # Fetch unmastered mistakes using the repository
            return self.mistake_repo.get_user_mistakes(user_id, status={"$ne": "MASTERED"})
            
        except Exception as e:
            logger.error(f"Error fetching unmastered mistakes: {str(e)}")
            return []
    
    def get_mistakes_for_practice(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve mistakes for practice.
        
        This method matches the class diagram's getMistakesForPractice method.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of mistakes to return
            
        Returns:
            List of mistakes for practice
        """
        now = datetime.utcnow()
        
        try:
            # Fetch practice-due mistakes using the repository
            mistakes = self.mistake_repo.get_mistakes_for_practice(user_id, limit)
            
            # Transform into practice exercises
            return [self._transform_to_practice_item(mistake) for mistake in mistakes]
            
        except Exception as e:
            logger.error(f"Error fetching practice items: {str(e)}")
            return []
    
    def get_mistake_statistics(self, user_id: str) -> MistakeStatistics:
        """
        Get statistics about a user's mistakes.
        
        This method matches the class diagram's getMistakeStatistics method.
        
        Args:
            user_id: ID of the user
            
        Returns:
            MistakeStatistics object with statistics
        """
        try:
            now = datetime.utcnow()
            user_object_id = ObjectId(user_id)
            
            # Get counts by status
            total_count = self.mistake_repo.count({"user_id": user_object_id})
            mastered_count = self.mistake_repo.count({"user_id": user_object_id, "status": "MASTERED"})
            learning_count = self.mistake_repo.count({"user_id": user_object_id, "status": "LEARNING"})
            new_count = self.mistake_repo.count({"user_id": user_object_id, "status": "NEW"})
            
            # Get type distribution
            grammar_count = self.mistake_repo.count({"user_id": user_object_id, "type": "GRAMMAR"})
            vocab_count = self.mistake_repo.count({"user_id": user_object_id, "type": "VOCABULARY"})
            
            # Get due for practice
            due_count = self.mistake_repo.count({
                "user_id": user_object_id,
                "next_practice_date": {"$lte": now},
                "status": {"$ne": "MASTERED"}
            })
            
            # Calculate mastery percentage
            mastery_percentage = 0
            if total_count > 0:
                mastery_percentage = (mastered_count / total_count) * 100
            
            return MistakeStatistics(
                total_count=total_count,
                mastered_count=mastered_count,
                learning_count=learning_count,
                new_count=new_count,
                type_distribution={
                    "GRAMMAR": grammar_count,
                    "VOCABULARY": vocab_count
                },
                due_for_practice=due_count,
                mastery_percentage=mastery_percentage
            )
            
        except Exception as e:
            logger.error(f"Error getting mistake statistics: {str(e)}")
            return MistakeStatistics()
    
    def update_after_practice(
        self,
        mistake_id: str, 
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update mistake after practice.
        
        This method matches the class diagram's updateAfterPractice method.
        
        Args:
            mistake_id: ID of the mistake
            result: Practice result data including user_id, was_successful, and user_answer
            
        Returns:
            Updated mistake information
        """
        try:
            was_successful = result.get("was_successful", False)
            
            # Use the repository to update the practice result
            updated_mistake = self.mistake_repo.update_practice_result(mistake_id, was_successful)

            if not updated_mistake:
                return {"error": "Mistake not found or failed to update"}
            
            # The user_answer is not part of the repository logic, so we add it here if needed
            user_answer = result.get("user_answer", "")
            if user_answer:
                self.mistake_repo.update(mistake_id, {"last_answer": user_answer})
                updated_mistake["last_answer"] = user_answer
            
            # Add feedback
            updated_mistake["feedback"] = self._generate_practice_feedback(updated_mistake, was_successful)
            
            return updated_mistake
                
        except Exception as e:
            logger.error(f"Error updating after practice: {str(e)}")
            raise
    
    def create_practice_session(
        self, 
        user_id: str, 
        mistakes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a new practice session.
        
        This method matches the class diagram's createPracticeSession method.
        
        Args:
            user_id: ID of the user
            mistakes: List of mistakes to include in the session
            
        Returns:
            Created practice session
        """
        try:
            # Create practice session record
            session = {
                "_id": ObjectId(),
                "user_id": ObjectId(user_id),
                "started_at": datetime.utcnow(),
                "completed_at": None,
                "mistakes_practiced": [],
                "created_at": datetime.utcnow()
            }
            
            # Insert session
            db.practice_sessions.insert_one(session)
            
            # Format for response
            session["_id"] = str(session["_id"])
            session["user_id"] = str(session["user_id"])
            session["mistake_ids"] = [m.get("_id") for m in mistakes]
            
            return session
            
        except Exception as e:
            logger.error(f"Error creating practice session: {str(e)}")
            raise
    
    def _extract_context(self, transcription: str, text: str) -> str:
        """
        Extract text surrounding the mistake for context.
        
        Args:
            transcription: Full transcription text
            text: The specific text with the mistake
            
        Returns:
            Context string with mistake highlighted
        """
        if not text or text not in transcription:
            return transcription
        
        # Find position of the mistake
        pos = transcription.find(text)
        
        # Get surrounding text (50 chars before and after)
        start = max(0, pos - 50)
        end = min(len(transcription), pos + len(text) + 50)
        
        # Create context with highlighted mistake
        context = transcription[start:end]
        highlighted = context.replace(text, f"[{text}]")
        
        return highlighted
    
    def _extract_situation_context(self, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Extract relevant situation info from context.
        
        Args:
            context: Conversation context
            
        Returns:
            Dictionary with relevant context information
        """
        if not context:
            return None
        
        return {
            "user_role": context.get("user_role"),
            "ai_role": context.get("ai_role"),
            "situation": context.get("situation")
        }
    
    def _calculate_next_practice_date(self, practice_count: int, was_successful: bool) -> datetime:
        """
        Calculate next practice date using spaced repetition.
        
        This method matches the class diagram's calculateNextPracticeDate method.
        
        Args:
            practice_count: Number of times this mistake has been practiced
            was_successful: Whether the last practice was successful
            
        Returns:
            Datetime for next practice
        """
        now = datetime.utcnow()
        
        # New mistake - practice soon
        if practice_count == 0:
            return now + timedelta(hours=2)
        
        # Failed practice - retry soon
        if not was_successful:
            return now + timedelta(hours=4)
        
        # Successful practice - gradually increase interval
        interval_days = min(2 ** practice_count, 30)  # Cap at 30 days
        return now + timedelta(days=interval_days)
    
    # Alias for backward compatibility
    _calculate_next_practice = _calculate_next_practice_date
    
    def _store_unique_mistakes(self, user_id: str, mistakes: List[Dict[str, Any]]) -> List[str]:
        """
        Create or update unique mistakes using the repository.
        
        Args:
            user_id: ID of the user
            mistakes: List of mistake data
            
        Returns:
            List of IDs of stored mistakes
        """
        stored_ids = []
        for mistake in mistakes:
            try:
                # Use the repository to upsert the mistake
                mistake_id = self.mistake_repo.upsert_mistake(mistake)
                stored_ids.append(mistake_id)
            except Exception as e:
                logger.error(f"Error storing unique mistake: {str(e)}")
        
        return stored_ids
    
    def _transform_to_practice_item(self, mistake: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a mistake into a practice item.
        
        Args:
            mistake: The mistake to transform
            
        Returns:
            Practice item
        """
        # Convert ObjectId to string
        mistake_copy = mistake.copy()
        mistake_copy["_id"] = str(mistake_copy["_id"]) 
        mistake_copy["user_id"] = str(mistake_copy["user_id"])
        
        # Add practice prompt
        mistake_copy["practice_prompt"] = self._generate_practice_prompt(mistake)
        
        return mistake_copy
    
    def _generate_practice_prompt(self, mistake: Dict[str, Any]) -> str:
        """
        Generate a prompt for practicing this mistake.
        
        Args:
            mistake: Mistake data
            
        Returns:
            Practice prompt string
        """
        if mistake["type"] == "GRAMMAR":
            return f"Correct the grammar in this sentence: \"{mistake['context']}\""
        
        elif mistake["type"] == "VOCABULARY":
            return f"Improve this sentence by using a better word or phrase for '{mistake['original_text']}': \"{mistake['context']}\""
        
        return f"Practice this mistake: {mistake['original_text']}"
    
    def _generate_practice_feedback(self, mistake: Dict[str, Any], was_successful: bool) -> str:
        """
        Generate feedback for practice attempt.
        
        Args:
            mistake: Mistake data
            was_successful: Whether the practice was successful
            
        Returns:
            Feedback string
        """
        if was_successful:
            return f"Great job! You've correctly used '{mistake['correction']}' instead of '{mistake['original_text']}'."
        else:
            return f"Keep practicing! Remember to use '{mistake['correction']}' instead of '{mistake['original_text']}'. {mistake['explanation']}"
    
    def extract_and_store_mistakes(
        self,
        user_id: str,
        transcription: str,
        feedback: Dict[str, Any]
    ) -> int:
        """
        Extract mistakes from a feedback record and store them.
        
        This method is a specialized version of process_feedback_for_mistakes
        designed to work with direct feedback database records.
        
        Args:
            user_id: ID of the user
            transcription: Original transcription text
            feedback: Feedback record from database
            
        Returns:
            Number of mistakes processed
        """
        return self.process_feedback_for_mistakes(user_id, transcription, feedback) 