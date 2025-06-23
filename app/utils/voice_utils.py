"""
Voice-related utility functions.
"""
import random

MALE_VOICES = ["im_nicola", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_v0adam", "hm_omega", "bm_daniel", "bm_fable", "bm_george", "bm_lewis", "bm_v0george", "bm_v0lewis"]
FEMALE_VOICES = ["af_aoede", "af_heart", "bf_v0isabella"]

def pick_suitable_voice_name(gender: str) -> str:
    """   
    Returns a random voice name based on the specified gender.
    """
    if "f" in gender.lower():
        return random.choice(FEMALE_VOICES)
    return random.choice(MALE_VOICES) 