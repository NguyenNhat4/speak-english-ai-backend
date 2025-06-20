from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from app.routes import user_routes, image_description
from app.routes import conversation_routes, audio_routes, message_routes, tts_routes
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.models import SecurityScheme
from fastapi.security import OAuth2PasswordBearer
from typing import Dict
from app.utils.event_handler import event_handler
from app.config.settings import settings
# Audio processing now handled by AudioService
import logging
from pathlib import Path

app = FastAPI(
    title=settings.app_name,
    description="""
    API for the Speak AI application.
    
    ## Authentication
    This API uses OAuth2 with JWT tokens for authentication.
    
    To authenticate:
    1. Use the `/api/users/login` endpoint with your email and password
    2. Use the received token in the Authorize dialog (click the 🔓 button)
    
    ## Authorization
    The API uses role-based access control with two main roles:
    * **user**: Basic access to own profile and conversations
    * **admin**: Full access including user management
    """,
    version=settings.app_version,
    debug=settings.debug_mode,
    openapi_tags=[
        {
            "name": "users",
            "description": "Operations with users. Includes registration, authentication, and profile management."
        },
        {
            "name": "conversations",
            "description": "Operations with conversations. Requires authentication."
        },
        {
            "name": "audio",
            "description": "Operations for audio processing and speech-to-text conversion."
        },
        {
            "name": "messages",
            "description": "Operations for message handling and AI responses."
        },
        {
            "name": "tts",
            "description": "Operations for text-to-speech conversion and voice context."
        },
        {
            "name": "images",
            "description": "Operations for image processing and description."
        },
        {
            "name": "feedback",
            "description": "Operations for generating and managing language feedback."
        },
        {
            "name": "mistakes",
            "description": "Operations for tracking and drilling language mistakes."
        }
    ]
)

# Configure security scheme for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/users/login",
    scopes={
        "user": "Read/write access to private user data",
        "admin": "Full access to all operations"
    }
)

# Configure CORS middleware with centralized settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if isinstance(settings.cors_origins, list) else [settings.cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(
    user_routes.router,
    prefix="/api/users",
    tags=["users"],
    responses={401: {"description": "Unauthorized"}}
)

app.include_router(
    conversation_routes.router,
    prefix="/api",
    tags=["conversations"],
    responses={401: {"description": "Unauthorized"}}
)

app.include_router(
    audio_routes.router,
    prefix="/api",
    tags=["audio"],
    responses={401: {"description": "Unauthorized"}}
)

app.include_router(
    message_routes.router,
    prefix="/api",
    tags=["messages"],
    responses={401: {"description": "Unauthorized"}}
)

app.include_router(
    tts_routes.router,
    prefix="/api",
    tags=["tts"],
    responses={401: {"description": "Unauthorized"}}
)

app.include_router(
    image_description.router,
    prefix="/api",
    tags=["images"],
    responses={401: {"description": "Unauthorized"}}
)

# Mount the uploads directory for serving images
uploads_path = Path(__file__).parent / "uploads"
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint that returns a welcome message.
    
    Returns:
        dict: A dictionary containing a welcome message for the FastAPI + MongoDB project.
    """
    return {
        "message": "Welcome to Speak AI API",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json"
    }

@app.on_event("startup")
async def startup_event():
    """
    Function that runs on application startup.
    Starts the background task processor.
    """
    # Start the event handler
    event_handler.start()

@app.on_event("shutdown")
async def shutdown_event():
    """
    Function that runs on application shutdown.
    Stops the background task processor.
    """
    # Stop the event handler
    event_handler.stop()





