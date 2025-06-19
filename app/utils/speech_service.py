# DEPRECATED: This module has been consolidated into app.services.audio_service
# Please use AudioService for all audio processing functionality
# This file is kept for backward compatibility only

import warnings
warnings.warn(
    "speech_service module is deprecated. Use app.services.audio_service.AudioService instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import the new service for backward compatibility
from app.services.audio_service import AudioService

# Alias for backward compatibility - redirect all usage to AudioService
class SpeechService(AudioService):
    """
    DEPRECATED: Use AudioService directly instead.
    
    This class exists only for backward compatibility.
    All functionality has been moved to AudioService.
    """
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "SpeechService is deprecated. Use AudioService directly.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)