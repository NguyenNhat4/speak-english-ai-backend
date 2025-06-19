import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from bson import ObjectId
import threading
import queue

from app.config.database import db
# Updated import path after mistake service was moved
# from app.services.mistake_service import MistakeService

logger = logging.getLogger(__name__)

# Task queue for background processing
task_queue = queue.Queue()

class EventHandler:
    """
    Handler for background event processing and task scheduling.
    
    This class provides functionality to:
    1. Process events asynchronously
    2. Schedule tasks for future execution
    3. Manage a task queue for efficient processing
    """
    
    def __init__(self):
        # Temporarily disabled - will be re-enabled when mistake service is implemented
        # self.mistake_service = MistakeService()
        self.mistake_service = None
        self.running = False
        self.worker_thread = None
    
    def start(self):
        """Start the background event processing thread."""
        if self.running:
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        logger.info("Background event handler started")
    
    def stop(self):
        """Stop the background event processing thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Background event handler stopped")
    
    def on_new_feedback(self, feedback_id: str, user_id: Optional[str] = None, transcription: Optional[str] = None):
        """
        Handle a new feedback event.
        
        Args:
            feedback_id: ID of the newly created feedback record
            user_id: Optional user ID associated with the feedback
            transcription: Optional transcription text associated with the feedback
        """
        logger.info(f"Received new feedback event for feedback_id: {feedback_id}")
        
        try:
            # Schedule task to process this feedback for mistakes
            task_data = {
                "feedback_id": feedback_id
            }
            
            # Add additional data if provided
            if user_id:
                task_data["user_id"] = user_id
            
            if transcription:
                task_data["transcription"] = transcription
            
            self.schedule_task(
                task_name="process_feedback_for_mistakes",
                data=task_data,
                delay_in_seconds=0  # Process immediately
            )
        except Exception as e:
            logger.error(f"Error scheduling feedback processing: {str(e)}")
    
    def schedule_task(self, task_name: str, data: Dict[str, Any], delay_in_seconds: int = 0) -> str:
        """
        Schedule a task for future execution.
        
        Args:
            task_name: Name of the task to execute
            data: Data to pass to the task
            delay_in_seconds: Delay before executing the task
            
        Returns:
            ID of the scheduled task
            
        Raises:
            SchedulingError: If task scheduling fails
        """
        try:
            # Generate task ID
            task_id = str(ObjectId())
            
            # Calculate execution time
            execution_time = datetime.utcnow() + timedelta(seconds=delay_in_seconds)
            
            # Create task record
            task = {
                "_id": ObjectId(task_id),
                "task_name": task_name,
                "data": data,
                "scheduled_time": execution_time,
                "status": "pending",
                "created_at": datetime.utcnow()
            }
            
            # Store in database
            db.scheduled_tasks.insert_one(task)
            
            # Add to in-memory queue if delay is small
            if delay_in_seconds < 300:  # Less than 5 minutes
                task_queue.put((execution_time, task_id, task_name, data))
                
            return task_id
                
        except Exception as e:
            logger.error(f"Error scheduling task: {str(e)}")
            raise Exception(f"Failed to schedule task: {str(e)}")
    
    def process_queued_tasks(self):
        """Process all queued tasks that are due for execution."""
        try:
            now = datetime.utcnow()
            
            # Find tasks due for execution
            due_tasks = db.scheduled_tasks.find({
                "scheduled_time": {"$lte": now},
                "status": "pending"
            })
            
            # Process each task
            for task in due_tasks:
                try:
                    # Mark as processing
                    db.scheduled_tasks.update_one(
                        {"_id": task["_id"]},
                        {"$set": {"status": "processing", "started_at": now}}
                    )
                    
                    # Process task based on task name
                    self._execute_task(task["task_name"], task["data"])
                    
                    # Mark as completed
                    db.scheduled_tasks.update_one(
                        {"_id": task["_id"]},
                        {"$set": {"status": "completed", "completed_at": datetime.utcnow()}}
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing task {task['_id']}: {str(e)}")
                    
                    # Mark as failed
                    db.scheduled_tasks.update_one(
                        {"_id": task["_id"]},
                        {
                            "$set": {
                                "status": "failed",
                                "error": str(e),
                                "failed_at": datetime.utcnow()
                            }
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Error processing queued tasks: {str(e)}")
    
    def _process_queue(self):
        """Worker thread function to process the task queue."""
        while self.running:
            try:
                # Process database tasks
                self.process_queued_tasks()
                
                # Process in-memory queue
                now = datetime.utcnow()
                
                # Check if there are tasks to process
                if not task_queue.empty():
                    # Get the next task but don't remove it yet
                    execution_time, task_id, task_name, data = task_queue.queue[0]
                    
                    # If it's time to execute
                    if execution_time <= now:
                        # Remove from queue
                        task_queue.get()
                        
                        try:
                            # Execute the task
                            self._execute_task(task_name, data)
                            
                            # Update task status in database
                            db.scheduled_tasks.update_one(
                                {"_id": ObjectId(task_id)},
                                {"$set": {"status": "completed", "completed_at": datetime.utcnow()}}
                            )
                            
                        except Exception as e:
                            logger.error(f"Error executing task {task_id}: {str(e)}")
                            
                            # Update task status in database
                            db.scheduled_tasks.update_one(
                                {"_id": ObjectId(task_id)},
                                {
                                    "$set": {
                                        "status": "failed",
                                        "error": str(e),
                                        "failed_at": datetime.utcnow()
                                    }
                                }
                            )
                
                # Sleep to avoid high CPU usage
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in task processing thread: {str(e)}")
                time.sleep(5)  # Sleep longer on error
    
    def _execute_task(self, task_name: str, data: Dict[str, Any]):
        """
        Execute a task based on its name.
        
        Args:
            task_name: Name of the task to execute
            data: Data to pass to the task
            
        Raises:
            ValueError: If task name is unknown
        """
        if task_name == "process_feedback_for_mistakes":
            # Temporarily disabled until mistake service is implemented
            logger.info(f"Mistake processing temporarily disabled for feedback: {data.get('feedback_id')}")
            return
            
        elif task_name == "calculate_next_practice_dates":
            # Temporarily disabled until mistake service is implemented
            logger.info(f"Practice date calculation temporarily disabled for user: {data.get('user_id')}")
            return
            
        else:
            raise ValueError(f"Unknown task name: {task_name}")

# Create a singleton instance
event_handler = EventHandler() 