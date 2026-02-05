"""
Transcript extraction service.
Tries YouTube captions first (free, instant), falls back to AI transcription.
Supports multiple AI providers: SiliconFlow, Replicate.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

from app.config import get_settings
from app.services.user_settings import get_cookies_browser

logger = logging.getLogger(__name__)


def _ensure_js_runtime_in_path():
    """Ensure a JavaScript runtime is in PATH for yt-dlp's n-challenge solver."""
    # Check common Node.js locations (mise, nvm, homebrew, system)
    node_paths = [
        Path.home() / ".local" / "share" / "mise" / "installs" / "node",  # mise
        Path.home() / ".nvm" / "versions" / "node",  # nvm
        Path("/opt/homebrew/opt/node/bin"),  # Homebrew Apple Silicon
        Path("/usr/local/opt/node/bin"),  # Homebrew Intel
        Path.home() / ".deno" / "bin",  # deno fallback
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


class TranscriptionError(Exception):
    """Exception raised when transcription fails with a specific error."""
    pass


async def _get_local_whisper_transcription(video_id: str) -> 'AudioTranscriptResult':
    """
    Try local Whisper transcription if a model is installed.
    Returns None if no model installed, raises TranscriptionError on actual failure.
    """
    from app.services.whisper_local import (
        transcribe_audio as whisper_transcribe,
        has_any_model_installed,
        TranscriptionError as WhisperError,
    )

    if not has_any_model_installed():
        logger.info("No local Whisper model installed, skipping")
        return None

    try:
        logger.info(f"Trying local Whisper transcription for {video_id}")
        return await whisper_transcribe(video_id)
    except WhisperError as e:
        # Log but don't raise - let cloud APIs handle it
        logger.warning(f"Local Whisper failed: {e}")
        return None


async def _get_ai_transcription(video_id: str, provider: str = None) -> 'AudioTranscriptResult':
    """
    Get AI transcription using local Whisper first, then cloud providers.

    Priority:
    1. Local Whisper (if model installed)
    2. Cloud APIs (Replicate/SiliconFlow)

    Raises TranscriptionError on failure.
    """
    # Try local Whisper first
    local_result = await _get_local_whisper_transcription(video_id)
    if local_result:
        return local_result

    # Fall back to cloud APIs
    settings = get_settings()
    if not provider:
        provider = settings.transcription_provider.lower()
    else:
        provider = provider.lower()

    logger.info(f"Using cloud transcription provider: {provider}")

    if provider == "replicate":
        from app.services.replicate_transcribe import transcribe_audio, TranscriptionError as ReplicateError
        try:
            return await transcribe_audio(video_id)
        except ReplicateError as e:
            raise TranscriptionError(str(e))
    elif provider == "siliconflow":
        from app.services.siliconflow_transcribe import transcribe_audio, TranscriptionError as SiliconFlowError
        try:
            return await transcribe_audio(video_id)
        except SiliconFlowError as e:
            raise TranscriptionError(str(e))
    else:
        # No cloud provider configured and no local model
        from app.services.whisper_local import has_any_model_installed
        if not has_any_model_installed():
            raise TranscriptionError(
                "No transcription method available. Download a Whisper model in settings, "
                "or configure a cloud API (Replicate/SiliconFlow)."
            )
        raise TranscriptionError(f"Unknown transcription provider: {provider}")


# Import for type hints only
from app.services.siliconflow_transcribe import AudioTranscriptResult

# Thread pool for running yt-dlp (which is synchronous)
_executor = ThreadPoolExecutor(max_workers=2)


class TranscriptResult:
    def __init__(
        self,
        content: str,
        language: str,
        word_count: int,
        method: str = "caption",  # "caption" for YouTube CC, "ai" for SiliconFlow
    ):
        self.content = content
        self.language = language
        self.word_count = word_count
        self.method = method


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _extract_caption_sync(video_id: str) -> Optional[TranscriptResult]:
    """Synchronous function to extract captions using yt-dlp."""
    _ensure_js_runtime_in_path()
    from app.config import get_settings
    settings = get_settings()

    video_url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        # Support multiple languages
        'subtitleslangs': ['all'],  # Fetch all available languages, filter in code
        'subtitlesformat': 'json3',
        'cookiesfrombrowser': (get_cookies_browser(),),
        'js_runtimes': {'node': {}},  # Enable Node.js for YouTube n-challenge
    }

    # Add proxy if configured
    if settings.proxy_url:
        ydl_opts['proxy'] = settings.proxy_url

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

            if not info:
                return None

            # Try to get subtitles (manual first, then automatic)
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})

            # Debug: log available languages
            logger.info(f"Available manual subtitles: {list(subtitles.keys())}")
            logger.info(f"Available automatic captions: {list(automatic_captions.keys())}")

            # Priority order for languages
            lang_priority = [
                'en', 'en-US', 'en-GB',
                'it', 'it-IT',
                'zh', 'zh-Hans', 'zh-Hant', 'zh-TW', 'zh-HK',
                'ja', 'ko'
            ]

            sub_data = None
            language = 'unknown'

            # Check manual subtitles first
            for lang in lang_priority:
                if lang in subtitles:
                    sub_info = subtitles[lang]
                    for fmt in sub_info:
                        if fmt.get('ext') == 'json3':
                            sub_data = fmt
                            language = lang
                            break
                    if sub_data:
                        break

            # Fall back to automatic captions
            if not sub_data:
                for lang in lang_priority + ['en-orig']:
                    if lang in automatic_captions:
                        sub_info = automatic_captions[lang]
                        for fmt in sub_info:
                            if fmt.get('ext') == 'json3':
                                sub_data = fmt
                                language = lang
                                break
                        if sub_data:
                            break

            if not sub_data:
                return None

            # Download the subtitle content
            sub_url = sub_data.get('url')
            if not sub_url:
                return None

            import urllib.request
            import json

            with urllib.request.urlopen(sub_url, timeout=30) as response:
                sub_content = json.loads(response.read().decode('utf-8'))

            # Parse json3 format and build transcript
            events = sub_content.get('events', [])
            transcript_lines = []
            full_text_parts = []

            for event in events:
                if 'segs' not in event:
                    continue

                start_time = event.get('tStartMs', 0) / 1000
                text_parts = []

                for seg in event['segs']:
                    text = seg.get('utf8', '')
                    if text and text.strip():
                        text_parts.append(text)

                if text_parts:
                    text = ''.join(text_parts).strip()
                    if text:
                        timestamp = _format_timestamp(start_time)
                        transcript_lines.append(f"[{timestamp}] {text}")
                        full_text_parts.append(text)

            if not transcript_lines:
                return None

            content = '\n'.join(transcript_lines)
            full_text = ' '.join(full_text_parts)
            word_count = len(full_text.split())

            return TranscriptResult(
                content=content,
                language=language,
                word_count=word_count,
                method="caption",
            )

    except Exception as e:
        logger.error(f"Error extracting captions for {video_id}: {e}")
        return None


async def extract_transcript(
    video_id: str,
    use_ai_fallback: bool = True,
    provider: str = None,
) -> Optional[TranscriptResult]:
    """
    Extract transcript from a YouTube video.

    First tries YouTube captions (free, instant).
    If no captions and use_ai_fallback=True, uses AI transcription.

    Args:
        video_id: YouTube video ID
        use_ai_fallback: Whether to use AI transcription if no captions available
        provider: AI provider to use ("replicate" or "siliconflow")

    Returns:
        TranscriptResult object or None if no transcript available
    """
    # Try YouTube captions first
    logger.info(f"Attempting caption extraction for {video_id}")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _extract_caption_sync, video_id)

    if result:
        logger.info(f"Caption extraction successful for {video_id} ({result.method})")
        return result

    # No captions available, try AI transcription
    if use_ai_fallback:
        logger.info(f"No captions found for {video_id}, trying AI transcription")
        # Let TranscriptionError propagate up
        ai_result = await _get_ai_transcription(video_id, provider=provider)

        return TranscriptResult(
            content=ai_result.content,
            language=ai_result.language,
            word_count=ai_result.word_count,
            method=ai_result.method,
        )

    logger.warning(f"No transcript available for {video_id}")
    return None


async def extract_transcript_caption_only(video_id: str) -> Optional[TranscriptResult]:
    """
    Extract transcript using only YouTube captions (no AI fallback).
    Use this for bulk extraction to avoid using AI quota.
    Returns None if no captions available (does not raise error).
    """
    # Try YouTube captions first
    logger.info(f"Attempting caption-only extraction for {video_id}")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _extract_caption_sync, video_id)

    if result:
        logger.info(f"Caption extraction successful for {video_id}")
        return result

    logger.info(f"No captions available for {video_id}")
    return None
