"""
Centralized Configuration Management for SpeakAI Backend

This module provides a centralized, type-safe configuration management system
using Pydantic BaseSettings with proper validation and security features.
"""

import os
from typing import Optional, List, Union
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings
from pathlib import Path


class ApplicationConfig(BaseSettings):
    """
    Centralized application configuration with validation and type safety.
    
    All environment variables are defined here with proper types,
    validation, and secure defaults (no dangerous fallbacks).
    """
    
    # Database Configuration
    mongodb_url: str = Field(description="MongoDB connection string")
    database_name: str = Field(description="MongoDB database name")
    
    # Security Configuration
    jwt_secret_key: SecretStr = Field(description="JWT secret key (minimum 32 characters)", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="JWT token expiration in minutes",
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="JWT refresh token expiration in days",
        alias="REFRESH_TOKEN_EXPIRE_DAYS"
    )
    
    # AI Services Configuration
    gemini_api_key: SecretStr = Field(description="Google Gemini API key", alias="GEMINI_API_KEY")
    gemini_model_name: str = Field(default="gemini-1.5-flash", description="Google Gemini model name", alias="GEMINI_MODEL_NAME")
    
    # Azure Speech Services Configuration
    azure_speech_key: Optional[SecretStr] = Field(None, description="Azure Speech Services API key", alias="AZURE_SPEECH_KEY")
    azure_speech_region: str = Field(default="eastus", description="Azure Speech Services region", alias="AZURE_SPEECH_REGION")
    
    # TTS Configuration
    tts_backend_base_url: str = Field(default="http://tts_kokoro:8880", description="TTS backend service URL", alias="TTS_BACKEND_BASE_URL")
    
    # Application Configuration
    debug_mode: bool = Field(default=False, description="Enable debug mode", alias="DEBUG")
    log_level: str = Field(default="INFO", description="Logging level", alias="LOG_LEVEL")
    app_name: str = Field(default="SpeakAI Backend", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    
    # File Upload Configuration
    upload_dir: str = Field(default="app/uploads", description="Directory for file uploads")
    max_upload_size: int = Field(default=50 * 1024 * 1024, description="Maximum file upload size in bytes")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host address", alias="API_HOST")
    api_port: int = Field(default=8000, description="API port", alias="API_PORT")
    cors_origins: Union[str, List[str]] = Field(default="*", description="CORS allowed origins (comma-separated)", alias="CORS_ORIGINS")
    
    # Performance Configuration
    worker_count: int = Field(default=1, description="Number of worker processes", alias="WORKER_COUNT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "forbid"
        
    @field_validator('jwt_secret_key')
    @classmethod
    def validate_jwt_secret(cls, v):
        """Validate JWT secret key meets minimum security requirements"""
        secret_value = v.get_secret_value()
        if len(secret_value) < 32:
            raise ValueError('JWT secret key must be at least 32 characters long for security')
        return v
    
    @field_validator('mongodb_url')
    @classmethod
    def validate_mongodb_url(cls, v):
        """Validate MongoDB URL format"""
        if not v.startswith(('mongodb://', 'mongodb+srv://')):
            raise ValueError('MongoDB URL must start with mongodb:// or mongodb+srv://')
        return v
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is supported"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of: {valid_levels}')
        return v.upper()
    
    @field_validator('cors_origins')
    @classmethod
    def validate_cors_origins(cls, v):
        """Process CORS origins"""
        if v == "*":
            return ["*"]
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    
    @field_validator('upload_dir')
    @classmethod
    def create_upload_dir(cls, v):
        """Create upload directory if it doesn't exist"""
        Path(v).mkdir(parents=True, exist_ok=True)
        return v
    
    def get_database_url(self) -> str:
        """Get the database URL as a regular string"""
        return self.mongodb_url
    
    def get_secret_key(self) -> str:
        """Get the JWT secret key as a regular string"""
        return self.jwt_secret_key.get_secret_value()
    
    def get_gemini_api_key(self) -> str:
        """Get the Gemini API key as a regular string"""
        return self.gemini_api_key.get_secret_value()
    
    def get_azure_speech_key(self) -> Optional[str]:
        """Get the Azure Speech API key as a regular string"""
        return self.azure_speech_key.get_secret_value() if self.azure_speech_key else None


# Global configuration instance
settings = ApplicationConfig()


def get_settings() -> ApplicationConfig:
    """
    Dependency function to get application settings.
    
    Can be used with FastAPI's dependency injection system.
    
    Returns:
        ApplicationConfig: The application configuration instance
    """
    return settings 