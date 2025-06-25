from app.routes.user_routes import router as user_controller
from app.routes.conversation_routes import router as conversation_controller
from app.routes.audio_routes import router as audio_controller
from app.routes.message_routes import router as message_controller
from app.routes.image_description import router as image_description_controller
from app.routes.tts_routes import router as tts_controller


__all__ = [
    'user_controller',
    'conversation_controller',
    'audio_controller',
    'message_controller',
    'tts_controller',
    'image_description_controller',
]
