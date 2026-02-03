"""
SiliconFlow speech-to-text service using SenseVoiceSmall model.
Used as fallback when YouTube captions are not available.
"""
import asyncio
import tempfile
import os
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import httpx
import yt_dlp

from app.config import get_settings
from app.services.user_settings import get_cookies_browser

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)

SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
SILICONFLOW_MODEL = "FunAudioLLM/SenseVoiceSmall"

# Supported audio formats
SUPPORTED_FORMATS = ['mp3', 'm4a', 'wav', 'webm', 'ogg']


class AudioTranscriptResult:
    def __init__(
        self,
        content: str,
        language: str,
        word_count: int,
        method: str = "ai",  # "ai" for SiliconFlow, "caption" for YouTube
        error: str = None,
    ):
        self.content = content
        self.language = language
        self.word_count = word_count
        self.method = method
        self.error = error


class TranscriptionError(Exception):
    """Exception raised when transcription fails with a specific error."""
    pass


def _download_audio_sync(video_id: str, output_dir: str) -> Optional[str]:
    """Download audio from YouTube video using yt-dlp."""
    from app.config import get_settings
    settings = get_settings()

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio/best',  # Flexible: any audio stream, or best overall if no separate audio
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        # Required to solve YouTube's JS challenges
        'extractor_args': {'youtube': {'player_client': ['web_creator']}},
        # Use Node.js for JS challenges
        'js_runtimes': {'node': {}},
        # Add cookies from browser (required for YouTube downloads due to bot detection)
        'cookiesfrombrowser': (get_cookies_browser(),),
    }

    # Add proxy if configured
    if settings.proxy_url:
        ydl_opts['proxy'] = settings.proxy_url

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Find the downloaded file
        audio_path = os.path.join(output_dir, f"{video_id}.mp3")
        if os.path.exists(audio_path):
            return audio_path

        # Check for other formats
        for ext in SUPPORTED_FORMATS:
            path = os.path.join(output_dir, f"{video_id}.{ext}")
            if os.path.exists(path):
                return path

        logger.error(f"Audio file not found after download for {video_id}")
        return None

    except Exception as e:
        logger.error(f"Error downloading audio for {video_id}: {e}")
        return None


async def _transcribe_with_siliconflow(audio_path: str, language: Optional[str] = None) -> Optional[dict]:
    """Send audio to SiliconFlow API for transcription.

    Args:
        audio_path: Path to audio file
        language: Optional language code (e.g., 'yue' for Cantonese, 'zh' for Chinese, 'en' for English)
                  If None, auto-detect language.

    Returns dict with 'text' and optionally 'language' if detected.
    """
    settings = get_settings()

    if not settings.siliconflow_api_key:
        logger.error("SILICONFLOW_API_KEY not configured")
        return None

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            with open(audio_path, 'rb') as audio_file:
                files = {'file': (os.path.basename(audio_path), audio_file, 'audio/mpeg')}
                # Use verbose_json to get language detection info
                # Do NOT translate - keep original language
                data = {
                    'model': SILICONFLOW_MODEL,
                    'response_format': 'verbose_json',
                }
                # Add language hint if provided (helps with accuracy)
                if language:
                    data['language'] = language
                    logger.info(f"Using language hint: {language}")

                headers = {'Authorization': f'Bearer {settings.siliconflow_api_key}'}

                response = await client.post(
                    SILICONFLOW_API_URL,
                    files=files,
                    data=data,
                    headers=headers,
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"SiliconFlow full response: {result}")
                    text = result.get('text', '')
                    # Log first 200 chars to see what language it's in
                    logger.info(f"Transcription preview: {text[:200]}...")
                    return {
                        'text': text,
                        'language': result.get('language', 'auto'),
                    }
                else:
                    error_text = response.text
                    logger.error(f"SiliconFlow API error: {response.status_code} - {error_text}")
                    if response.status_code == 401:
                        raise TranscriptionError("SiliconFlow: Invalid API key")
                    elif response.status_code == 402 or "insufficient" in error_text.lower():
                        raise TranscriptionError("SiliconFlow: Insufficient credit. Please top up your account.")
                    else:
                        raise TranscriptionError(f"SiliconFlow API error ({response.status_code}): {error_text[:100]}")

    except TranscriptionError:
        raise
    except Exception as e:
        logger.error(f"Error calling SiliconFlow API: {e}")
        raise TranscriptionError(f"SiliconFlow error: {str(e)[:200]}")


def _count_words(text: str) -> int:
    """Count words in text, handling both CJK and Latin scripts."""
    import re
    # For CJK text, count characters; for others, count words
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]', text))
    # Remove CJK for word count
    non_cjk = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]', ' ', text)
    latin_words = len(non_cjk.split())
    return cjk_chars + latin_words


async def transcribe_audio(video_id: str) -> Optional[AudioTranscriptResult]:
    """
    Download audio from YouTube and transcribe using SiliconFlow.

    Args:
        video_id: YouTube video ID

    Returns:
        AudioTranscriptResult or None if transcription failed
    """
    logger.info(f"Starting AI transcription for video {video_id}")

    # Create temp directory for audio file
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download audio
        loop = asyncio.get_event_loop()
        audio_path = await loop.run_in_executor(
            _executor,
            _download_audio_sync,
            video_id,
            temp_dir
        )

        if not audio_path:
            logger.error(f"Failed to download audio for {video_id}")
            return None

        file_size = os.path.getsize(audio_path)
        logger.info(f"Downloaded audio: {audio_path} ({file_size / 1024 / 1024:.1f} MB)")

        # Transcribe with SiliconFlow
        try:
            result = await _transcribe_with_siliconflow(audio_path)
        except TranscriptionError as e:
            logger.error(f"Transcription failed for {video_id}: {e}")
            raise

        if not result or not result.get('text'):
            logger.error(f"Failed to transcribe audio for {video_id}")
            raise TranscriptionError("No transcription result returned")

        text = result['text']
        detected_language = result.get('language', 'auto')
        word_count = _count_words(text)
        logger.info(f"Transcription complete for {video_id}: {word_count} words, language: {detected_language}")

        return AudioTranscriptResult(
            content=text,
            language=detected_language,
            word_count=word_count,
            method="ai",
        )
