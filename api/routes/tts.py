"""
ElevenLabs Text-to-Speech endpoint.
POST /tts/ — converts narrative text to audio, returns base64 mp3.
Falls back gracefully when no API key is configured.
"""
import os
import re
import base64
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George — deep, authoritative


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting for clean TTS input."""
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class TTSRequest(BaseModel):
    text: str
    voice_id: str = DEFAULT_VOICE_ID


@router.post("/")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech using ElevenLabs.
    Returns base64-encoded mp3 audio.
    If ELEVENLABS_API_KEY is not set, returns a flag for frontend fallback.
    """
    if not ELEVENLABS_API_KEY:
        return {
            "success": False,
            "fallback": True,
            "message": "ElevenLabs API key not configured — use Web Speech API",
        }

    clean_text = _strip_markdown(request.text)
    # Truncate to ~2500 chars (covers first 3 paragraphs, stays within free tier)
    if len(clean_text) > 2500:
        clean_text = clean_text[:2500].rsplit(' ', 1)[0] + '...'

    try:
        response = requests.post(
            f"{ELEVENLABS_BASE}/text-to-speech/{request.voice_id}",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "text": clean_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.2,
                    "use_speaker_boost": True,
                },
            },
            timeout=30,
        )
        response.raise_for_status()

        audio_base64 = base64.b64encode(response.content).decode("utf-8")
        return {
            "success": True,
            "fallback": False,
            "audio_base64": audio_base64,
            "content_type": "audio/mpeg",
        }

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            return {
                "success": False,
                "fallback": True,
                "message": "Invalid ElevenLabs API key — using Web Speech API",
            }
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
