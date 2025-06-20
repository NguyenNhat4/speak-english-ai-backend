"""
File utility functions for audio processing and validation.

This module centralizes all file-related operations to eliminate duplication
across services and routes.
"""

import logging
import shutil
import tempfile
from typing import Optional
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

# Audio file constants
VALID_AUDIO_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac']
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Upload directory
UPLOAD_DIR = Path("app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def validate_audio_file(file: UploadFile) -> None:
    """
    Validate audio file format and size.
    
    Args:
        file: The audio file to validate
        
    Raises:
        HTTPException: If validation fails
    """
    if not file:
        raise HTTPException(
            status_code=400,
            detail="No audio file provided"
        )
    
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )
    
    # Check file extension
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in VALID_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audio format. Supported formats: {', '.join(VALID_AUDIO_EXTENSIONS)}"
        )
    
    # Check filename length
    if len(file.filename) > 255:
        raise HTTPException(
            status_code=400,
            detail="Filename too long"
        )
    
    # Check file size if possible
    if hasattr(file.file, 'seek') and hasattr(file.file, 'tell'):
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB"
            )
    
    # Check size attribute if available
    if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    logger.debug(f"Audio file validation passed for: {file.filename}")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem
    """
    # Replace spaces and unsafe characters
    safe_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    sanitized = "".join(c if c in safe_chars else "_" for c in filename)
    
    # Replace multiple underscores/spaces with single underscore
    while "__" in sanitized or "  " in sanitized:
        sanitized = sanitized.replace("__", "_").replace("  ", " ")
    
    return sanitized.replace(" ", "_").strip("_")


def save_uploaded_file(file: UploadFile, user_id: str, category: str = "audio") -> Path:
    """
    Save an uploaded file to disk with proper organization.
    
    Args:
        file: The uploaded file
        user_id: ID of the user who owns the file
        category: File category for organization (default: "audio")
        
    Returns:
        Path to the saved file
        
    Raises:
        Exception: If file saving fails
    """
    # Validate the file first
    validate_audio_file(file)
    
    # Create user directory structure
    user_dir = UPLOAD_DIR / str(user_id) / category
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
    filename = file.filename or "unknown_file"
    safe_filename = sanitize_filename(f"{timestamp}_{filename}")
    file_path = user_dir / safe_filename
    
    # Save the file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    logger.info(f"Successfully saved file: {file_path}")
    return file_path


def cleanup_temp_file(file_path: Optional[str]) -> None:
    """
    Clean up temporary files to prevent disk space issues.
    
    Args:
        file_path: Path to the temporary file to delete
    """
    if file_path and Path(file_path).exists():
        try:
            Path(file_path).unlink()
            logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {file_path}: {str(e)}")


def create_temp_file(file: UploadFile, suffix: Optional[str] = None) -> Path:
    """
    Create a temporary file from uploaded file.
    
    Args:
        file: The uploaded file
        suffix: Optional file suffix
        
    Returns:
        Path to the temporary file
    """
    if suffix is None:
        suffix = Path(file.filename or "").suffix or ".tmp"
    
    # Create temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=suffix)
    temp_file_path = Path(temp_path)
    
    try:
        # Write uploaded file content to temp file
        with open(temp_fd, 'wb') as temp_file:
            shutil.copyfileobj(file.file, temp_file)
        
        logger.debug(f"Created temporary file: {temp_file_path}")
        return temp_file_path
        
    except Exception as e:
        # Clean up on error
        try:
            temp_file_path.unlink()
        except:
            pass
        raise e


def get_file_size(file_path: str) -> Optional[int]:
    """
    Get file size safely.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes, or None if error
    """
    try:
        return Path(file_path).stat().st_size
    except Exception as e:
        logger.warning(f"Could not get file size for {file_path}: {str(e)}")
        return None 