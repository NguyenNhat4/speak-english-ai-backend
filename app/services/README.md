# Audio Service Documentation

## Overview

The `AudioService` is a comprehensive service class that handles all audio-related operations in the SpeakAI application. This service consolidates functionality that was previously scattered across multiple utility files.

## Features

### 🎵 Audio File Management
- **File Upload & Validation**: Supports multiple audio formats (MP3, WAV, M4A, AAC, OGG, FLAC)
- **File Size Limits**: Maximum 50MB per file
- **Secure Storage**: Organized by user directories with timestamp-based naming
- **Database Integration**: Automatic audio record creation and management

### 🎤 Transcription Services
- **Multi-Method Transcription**: 
  - Whisper AI (default, works offline)
  - Google Speech Recognition (online fallback)
  - Google Cloud Speech-to-Text (enterprise fallback)
- **Language Support**: English and Vietnamese with automatic detection
- **Error Handling**: Graceful fallbacks when transcription fails
- **Temporary File Management**: Efficient memory usage with cleanup

### 🤖 AI-Powered Feedback
- **Grammar Analysis**: Identifies issues with severity levels (1-5)
- **Vocabulary Enhancement**: Suggests better alternatives with examples
- **Positive Reinforcement**: Highlights good language usage
- **Fluency Suggestions**: Provides tips for natural expression
- **Powered by Google Gemini**: Advanced language understanding

### 🛡️ Error Handling & Reliability
- **Graceful Degradation**: Multiple fallback mechanisms
- **Comprehensive Logging**: Detailed error tracking and debugging
- **Input Validation**: Thorough checks for all parameters
- **Resource Cleanup**: Automatic temporary file removal

## Usage Examples

### Basic Audio Transcription
```python
from app.services.audio_service import AudioService

audio_service = AudioService()

# Transcribe uploaded file
transcription, temp_path = audio_service.transcribe_audio(uploaded_file)

# Clean up
audio_service.cleanup_temp_file(temp_path)
```

### Complete Audio Processing with Feedback
```python
# Process audio for feedback
result = audio_service.process_audio_for_feedback(
    transcription="Hello, how are you today?",
    user_id="user_123",
    conversation_id="conv_456"
)

# Get feedback data
feedback = result["feedback"]
print(feedback["grammar"])      # Grammar issues
print(feedback["vocabulary"])   # Vocabulary suggestions
print(feedback["positives"])    # Positive aspects
print(feedback["fluency"])      # Fluency tips
```

### File Management
```python
# Save audio file
audio_id = audio_service.save_audio_file(uploaded_file, user_id)

# Get metadata
metadata = audio_service.get_audio_metadata(audio_id)
print(metadata["filename"])
print(metadata["file_size"])
```

## API Methods

### Core Transcription
- `transcribe_audio(file, language_code)` - Main transcription entry point
- `transcribe_from_upload(audio_file, language_code)` - Process uploaded files
- `transcribe_audio_local(audio_file_path, language_code)` - Google Speech API
- `transcribe_audio_with_whisper(audio_file_path, language_code)` - Whisper AI

### File Operations
- `save_audio_file(file, user_id)` - Save and create database record
- `validate_audio_file(file)` - Check format and size
- `cleanup_temp_file(file_path)` - Remove temporary files
- `get_audio_metadata(audio_id)` - Retrieve file information

### AI Processing
- `generate_feedback(user_text, reference_text)` - Generate language feedback
- `process_audio_for_feedback(transcription, user_id, conversation_id, audio_id)` - Complete processing pipeline

## Configuration

### Environment Variables
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### File Limits
- Maximum file size: 50MB
- Supported formats: .mp3, .wav, .m4a, .aac, .ogg, .flac
- Upload directory: `app/uploads/{user_id}/`

## Migration from Old Services

### Before (multiple files)
```python
from app.utils.audio_processor import transcribe_audio_with_whisper
from app.utils.speech_service import SpeechService
from app.utils.audio_processor import generate_feedback

# Multiple service instances and methods
```

### After (consolidated)
```python
from app.services.audio_service import AudioService

audio_service = AudioService()
# All functionality in one place
```

## Error Handling

The service provides multiple fallback mechanisms:

1. **Transcription Failures**: Falls back from Whisper → Speech Recognition → Cloud API
2. **AI Feedback Failures**: Returns basic positive feedback
3. **File Validation**: Clear error messages for unsupported formats
4. **Network Issues**: Graceful handling of API timeouts

## Performance Considerations

- **GPU Acceleration**: Automatically detects and uses CUDA when available
- **Memory Management**: Efficient temporary file handling
- **Async Support**: Compatible with FastAPI async endpoints
- **Caching**: Model loading is optimized for repeated use

## Dependencies

- `whisper` - OpenAI Whisper for offline transcription
- `torch` - PyTorch for ML model support
- `google-generativeai` - Gemini AI for feedback generation

## Testing

The service includes comprehensive error handling and logging for easy debugging. Monitor logs for transcription accuracy and performance metrics. 