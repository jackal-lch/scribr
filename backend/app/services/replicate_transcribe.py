"""
Replicate speech-to-text service using Whisper models.
Used as fallback when YouTube captions are not available.
"""
import asyncio
import tempfile
import os
import logging
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import replicate
import yt_dlp

from app.config import get_settings
from app.services.user_settings import get_cookies_browser

logger = logging.getLogger(__name__)


def _ensure_js_runtime_in_path():
    """Ensure a JavaScript runtime is in PATH for yt-dlp's n-challenge solver."""
    node_paths = [
        Path.home() / ".local" / "share" / "mise" / "installs" / "node",
        Path.home() / ".nvm" / "versions" / "node",
        Path("/opt/homebrew/opt/node/bin"),
        Path("/usr/local/opt/node/bin"),
        Path.home() / ".deno" / "bin",
    ]

    current_path = os.environ.get("PATH", "")

    for base_path in node_paths:
        if base_path.exists():
            if "mise" in str(base_path) or "nvm" in str(base_path):
                versions = sorted(base_path.iterdir(), reverse=True)
                for version_dir in versions:
                    bin_path = version_dir / "bin"
                    if bin_path.exists() and (bin_path / "node").exists():
                        if str(bin_path) not in current_path:
                            os.environ["PATH"] = f"{bin_path}:{current_path}"
                        return
            else:
                if str(base_path) not in current_path:
                    os.environ["PATH"] = f"{base_path}:{current_path}"
                return

_executor = ThreadPoolExecutor(max_workers=2)

# Use incredibly-fast-whisper for speed and cost efficiency
REPLICATE_MODEL = "vaibhavs10/incredibly-fast-whisper:3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c"

# Supported audio formats
SUPPORTED_FORMATS = ['mp3', 'm4a', 'wav', 'webm', 'ogg']


class AudioTranscriptResult:
    def __init__(
        self,
        content: str,
        language: str,
        word_count: int,
        method: str = "ai",
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
    _ensure_js_runtime_in_path()
    from app.config import get_settings
    settings = get_settings()

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")

    ydl_opts = {
        # Use bestaudio with fallback to best (for videos without separate audio streams)
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '64',  # Low quality is fine for speech
        }],
        'cookiesfrombrowser': (get_cookies_browser(),),
        'js_runtimes': {'node': {}},  # Enable Node.js for YouTube n-challenge
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


def _transcribe_with_replicate_sync(audio_path: str, language: Optional[str] = None) -> dict:
    """Send audio to Replicate API for transcription (sync version).

    Returns dict with 'text' and 'language' on success.
    Raises TranscriptionError on failure.
    """
    settings = get_settings()

    if not settings.replicate_api_token:
        raise TranscriptionError("REPLICATE_API_TOKEN not configured")

    # Create client with API token (avoids environment variable side effects)
    client = replicate.Client(api_token=settings.replicate_api_token)

    try:
        # Read audio file and create a file object
        with open(audio_path, 'rb') as audio_file:
            # Build input parameters
            input_params = {
                "audio": audio_file,
                "task": "transcribe",  # transcribe, not translate - keeps original language
                "batch_size": 64,
            }
            # Only add language if explicitly specified (otherwise auto-detect)
            if language:
                input_params["language"] = language

            # Run the model using the client instance
            output = client.run(
                REPLICATE_MODEL,
                input=input_params
            )

        logger.info(f"Replicate response: {output}")

        if output and 'text' in output:
            return {
                'text': output['text'],
                'language': output.get('language', language or 'auto'),
            }
        else:
            raise TranscriptionError(f"Unexpected response format from Replicate")

    except TranscriptionError:
        raise
    except Exception as e:
        error_msg = str(e)
        # Extract meaningful error message
        if "Insufficient credit" in error_msg:
            raise TranscriptionError("Replicate: Insufficient credit. Please add funds at replicate.com/account/billing")
        elif "401" in error_msg or "unauthorized" in error_msg.lower():
            raise TranscriptionError("Replicate: Invalid API token")
        else:
            raise TranscriptionError(f"Replicate API error: {error_msg[:200]}")


def _count_words(text: str) -> int:
    """Count words in text, handling both CJK and Latin scripts."""
    import re
    # For CJK text, count characters; for others, count words
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]', text))
    # Remove CJK for word count
    non_cjk = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]', ' ', text)
    latin_words = len(non_cjk.split())
    return cjk_chars + latin_words


async def transcribe_audio(video_id: str, language: Optional[str] = None) -> Optional[AudioTranscriptResult]:
    """
    Download audio from YouTube and transcribe using Replicate Whisper.

    Args:
        video_id: YouTube video ID
        language: Optional language code (e.g., 'yue' for Cantonese, 'zh' for Chinese)

    Returns:
        AudioTranscriptResult or None if transcription failed
    """
    logger.info(f"Starting Replicate transcription for video {video_id}")

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
            raise TranscriptionError("Failed to download audio from YouTube. The video may be restricted or unavailable.")

        file_size = os.path.getsize(audio_path)
        logger.info(f"Downloaded audio: {audio_path} ({file_size / 1024 / 1024:.1f} MB)")

        # Transcribe with Replicate
        try:
            result = await loop.run_in_executor(
                _executor,
                _transcribe_with_replicate_sync,
                audio_path,
                language
            )
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
