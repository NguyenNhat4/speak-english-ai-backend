import google.generativeai as genai
from app.config.settings import settings

# Configure Gemini AI with centralized settings
genai.configure(api_key=settings.get_gemini_api_key())

# Initialize the Gemini model
model = genai.GenerativeModel("gemini-2.0-flash")

def generate_response(prompt: str):
    """
    Generate a response from the Gemini AI model based on the provided prompt.
    
    Args:
        prompt (str): The input text prompt to generate a response for.
            Sample input:
            "You are an experienced interviewer, and the user is a job seeker. 
             The situation is: preparing for a software engineering job interview. 
             Here's the conversation so far:
             user: Tell me about your experience with Python
             Respond as an experienced interviewer."
    
    Returns:
        str: The generated response text from the Gemini model.
            Sample output:
            "I have extensive experience with Python, particularly in web development 
             using Django and Flask frameworks. I've worked on several large-scale 
             applications handling high traffic and complex data processing tasks. 
             Would you like me to elaborate on any specific aspect of my Python experience?"
        
    Raises:
        Exception: If there are any issues with the API call or response generation.
    """
    response = model.generate_content(prompt)
    return response.text

