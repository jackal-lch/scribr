"""
Local Whisper transcription service.
Auto-detects platform and uses:
- macOS (Apple Silicon): mlx-whisper (faster)
- Windows/Linux: faster-whisper (CPU/CUDA)
"""
import asyncio
import logging
import os
import platform
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import yt_dlp

from app.config import get_settings
from app.services.user_settings import get_cookies_browser, get_whisper_model

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)

# HuggingFace cache directory
HF_CACHE_DIR = Path.home() / ".cache" / "huggingface" / "hub"

# Supported audio formats
SUPPORTED_FORMATS = ['mp3', 'm4a', 'wav', 'webm', 'ogg']


def _is_apple_silicon() -> bool:
    """Check if running on Apple Silicon Mac."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _is_mlx_available() -> bool:
    """Check if mlx-whisper is available."""
    try:
        import mlx_whisper
        return True
    except ImportError:
        return False


def _get_backend() -> str:
    """
    Determine which backend to use.
    Returns 'mlx' or 'faster-whisper'.
    """
    if _is_apple_silicon() and _is_mlx_available():
        return "mlx"
    return "faster-whisper"


# Model configurations per backend
MLX_MODELS = {
    "turbo": {"size_mb": 800, "repo_id": "mlx-community/whisper-turbo"},
    "large-v3-turbo": {"size_mb": 1600, "repo_id": "mlx-community/whisper-large-v3-turbo"},
    "medium": {"size_mb": 1500, "repo_id": "mlx-community/whisper-medium-mlx"},
}

FASTER_WHISPER_MODELS = {
    "tiny": {"size_mb": 75, "repo_id": "Systran/faster-whisper-tiny"},
    "base": {"size_mb": 150, "repo_id": "Systran/faster-whisper-base"},
    "small": {"size_mb": 500, "repo_id": "Systran/faster-whisper-small"},
    "medium": {"size_mb": 1500, "repo_id": "Systran/faster-whisper-medium"},
    "large-v3": {"size_mb": 3000, "repo_id": "Systran/faster-whisper-large-v3"},
}


def get_whisper_models() -> dict:
    """Get models dict based on current backend."""
    if _get_backend() == "mlx":
        return MLX_MODELS
    return FASTER_WHISPER_MODELS


class TranscriptionError(Exception):
    """Exception raised when transcription fails."""
    pass


class AudioTranscriptResult:
    def __init__(
        self,
        content: str,
        language: str,
        word_count: int,
        method: str = "whisper-mlx",  # or "whisper-faster-whisper"
        error: str = None,
    ):
        self.content = content
        self.language = language
        self.word_count = word_count
        self.method = method
        self.error = error


def _get_model_cache_path(model_name: str) -> Optional[Path]:
    """Get the expected cache path for a model."""
    models = get_whisper_models()
    if model_name not in models:
        return None
    repo_id = models[model_name]["repo_id"]
    repo_dir = repo_id.replace("/", "--")
    return HF_CACHE_DIR / f"models--{repo_dir}"


def is_model_installed(model_name: str) -> bool:
    """Check if a Whisper model is installed in the HuggingFace cache."""
    models = get_whisper_models()
    if model_name not in models:
        return False
    cache_path = _get_model_cache_path(model_name)
    if not cache_path or not cache_path.exists():
        return False

    snapshots_dir = cache_path / "snapshots"
    if not snapshots_dir.exists():
        return False

    # Check if any snapshot has model files
    for snapshot in snapshots_dir.iterdir():
        if snapshot.is_dir():
            # MLX models use .safetensors, faster-whisper uses model.bin
            has_safetensors = any(f.suffix == '.safetensors' for f in snapshot.iterdir() if f.is_file())
            has_model_bin = (snapshot / "model.bin").exists()
            if has_safetensors or has_model_bin:
                return True
    return False


def get_installed_models() -> list[dict]:
    """
    Get list of all models with their install status.
    Returns list of dicts with name, size_mb, installed status, and backend info.
    """
    models = get_whisper_models()
    backend = _get_backend()
    result = []
    for name, config in models.items():
        result.append({
            "name": name,
            "size_mb": config["size_mb"],
            "installed": is_model_installed(name),
            "backend": backend,
        })
    return result


def get_backend_info() -> dict:
    """Get information about the current backend."""
    backend = _get_backend()
    return {
        "backend": backend,
        "platform": platform.system(),
        "arch": platform.machine(),
        "is_apple_silicon": _is_apple_silicon(),
        "mlx_available": _is_mlx_available(),
    }


def download_model(model_name: str, progress_callback=None):
    """
    Download a Whisper model on demand.
    Uses appropriate method based on backend.
    """
    models = get_whisper_models()
    if model_name not in models:
        raise TranscriptionError(f"Unknown model: {model_name}")

    if is_model_installed(model_name):
        logger.info(f"Model {model_name} is already installed")
        if progress_callback:
            progress_callback(100)
        return

    backend = _get_backend()
    logger.info(f"Downloading Whisper model: {model_name} (backend: {backend})")

    if progress_callback:
        progress_callback(0)

    try:
        if backend == "mlx":
            _download_mlx_model(model_name)
        else:
            _download_faster_whisper_model(model_name)

        if progress_callback:
            progress_callback(100)

        logger.info(f"Model {model_name} downloaded successfully")

    except Exception as e:
        logger.error(f"Failed to download model {model_name}: {e}")
        raise TranscriptionError(f"Failed to download model: {str(e)}")


def _download_mlx_model(model_name: str):
    """Download MLX model using huggingface_hub."""
    from huggingface_hub import snapshot_download
    repo_id = MLX_MODELS[model_name]["repo_id"]
    snapshot_download(repo_id=repo_id)


def _download_faster_whisper_model(model_name: str):
    """Download faster-whisper model by loading it."""
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    del model


def _download_audio_sync(video_id: str, output_dir: str) -> Optional[str]:
    """Download audio from YouTube video using yt-dlp."""
    settings = get_settings()

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '64',
        }],
        'extractor_args': {'youtube': {'player_client': ['web_creator']}},
        'js_runtimes': {'node': {}},
        'cookiesfrombrowser': (get_cookies_browser(),),
    }

    if settings.proxy_url:
        ydl_opts['proxy'] = settings.proxy_url

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        audio_path = os.path.join(output_dir, f"{video_id}.mp3")
        if os.path.exists(audio_path):
            return audio_path

        for ext in SUPPORTED_FORMATS:
            path = os.path.join(output_dir, f"{video_id}.{ext}")
            if os.path.exists(path):
                return path

        logger.error(f"Audio file not found after download for {video_id}")
        return None

    except Exception as e:
        logger.error(f"Error downloading audio for {video_id}: {e}")
        return None


def _transcribe_with_mlx(audio_path: str, model_name: str) -> dict:
    """Transcribe using MLX Whisper."""
    import mlx_whisper

    repo_id = MLX_MODELS[model_name]["repo_id"]
    logger.info(f"Transcribing with MLX model: {repo_id}")

    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=repo_id,
        language=None,  # Auto-detect
    )

    return {
        "text": result["text"],
        "language": result.get("language", "auto"),
    }


def _transcribe_with_faster_whisper(audio_path: str, model_name: str) -> dict:
    """Transcribe using faster-whisper."""
    from faster_whisper import WhisperModel

    logger.info(f"Transcribing with faster-whisper model: {model_name}")

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        language=None,
        task="transcribe",
    )

    text_parts = []
    for segment in segments:
        text_parts.append(segment.text.strip())

    return {
        "text": " ".join(text_parts),
        "language": info.language,
    }


def _transcribe_sync(audio_path: str, model_name: str) -> dict:
    """
    Transcribe audio using the appropriate backend.
    Returns dict with 'text' and 'language'.
    """
    if not is_model_installed(model_name):
        raise TranscriptionError(f"Model {model_name} is not installed")

    backend = _get_backend()

    try:
        if backend == "mlx":
            return _transcribe_with_mlx(audio_path, model_name)
        else:
            return _transcribe_with_faster_whisper(audio_path, model_name)
    except ImportError as e:
        raise TranscriptionError(f"Missing dependency: {e}")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise TranscriptionError(f"Transcription failed: {str(e)}")


def _count_words(text: str) -> int:
    """Count words in text, handling both CJK and Latin scripts."""
    import re
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]', text))
    non_cjk = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]', ' ', text)
    latin_words = len(non_cjk.split())
    return cjk_chars + latin_words


async def transcribe_audio(video_id: str) -> Optional[AudioTranscriptResult]:
    """
    Download audio from YouTube and transcribe using local Whisper.
    Auto-selects MLX on Apple Silicon, faster-whisper otherwise.
    """
    model_name = get_whisper_model()
    backend = _get_backend()

    if not is_model_installed(model_name):
        raise TranscriptionError(
            f"Whisper model '{model_name}' is not installed. Download it first in settings."
        )

    logger.info(f"Starting local Whisper transcription for {video_id} (model: {model_name}, backend: {backend})")

    with tempfile.TemporaryDirectory() as temp_dir:
        loop = asyncio.get_event_loop()

        # Download audio
        audio_path = await loop.run_in_executor(
            _executor,
            _download_audio_sync,
            video_id,
            temp_dir
        )

        if not audio_path:
            raise TranscriptionError("Failed to download audio from YouTube")

        file_size = os.path.getsize(audio_path)
        logger.info(f"Downloaded audio: {audio_path} ({file_size / 1024 / 1024:.1f} MB)")

        # Transcribe
        result = await loop.run_in_executor(
            _executor,
            _transcribe_sync,
            audio_path,
            model_name
        )

        if not result or not result.get('text'):
            raise TranscriptionError("No transcription result returned")

        text = result['text']
        language = result.get('language', 'auto')
        word_count = _count_words(text)

        logger.info(f"Transcription complete for {video_id}: {word_count} words, language: {language}")

        return AudioTranscriptResult(
            content=text,
            language=language,
            word_count=word_count,
            method=f"whisper-{backend}",
        )


def has_any_model_installed() -> bool:
    """Check if any Whisper model is installed."""
    models = get_whisper_models()
    for model_name in models:
        if is_model_installed(model_name):
            return True
    return False
