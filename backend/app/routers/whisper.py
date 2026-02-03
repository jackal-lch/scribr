"""
Whisper model management endpoints.
Allows listing, selecting, and downloading Whisper models for local transcription.
Auto-detects platform: MLX on Apple Silicon, faster-whisper on Windows/Linux.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.whisper_local import (
    get_whisper_models,
    get_installed_models,
    get_backend_info,
    is_model_installed,
    download_model,
    TranscriptionError,
)
from app.services.user_settings import (
    get_whisper_model,
    set_whisper_model,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=1)


class ModelInfo(BaseModel):
    name: str
    size_mb: int
    installed: bool


class ModelsResponse(BaseModel):
    selected_model: str
    models: list[ModelInfo]
    backend: str


class SelectModelRequest(BaseModel):
    model: str


@router.get("/whisper/models")
async def list_models():
    """List all available Whisper models with install status."""
    models = get_installed_models()
    backend_info = get_backend_info()
    return {
        "selected_model": get_whisper_model(),
        "models": models,
        "backend": backend_info["backend"],
        "backend_info": backend_info,
    }


@router.put("/whisper/model")
async def select_model(request: SelectModelRequest):
    """Select a Whisper model for transcription. Model must be installed."""
    model_name = request.model
    available_models = get_whisper_models()

    if model_name not in available_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Valid options: {', '.join(available_models.keys())}",
        )

    if not is_model_installed(model_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{model_name}' is not installed. Download it first.",
        )

    if not set_whisper_model(model_name):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save model selection",
        )

    return {"success": True, "model": model_name}


@router.post("/whisper/download/{model_name}")
async def download_whisper_model(model_name: str):
    """
    Download a Whisper model with SSE progress updates.
    Returns Server-Sent Events with download progress.
    """
    available_models = get_whisper_models()

    if model_name not in available_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown model: {model_name}. Valid options: {', '.join(available_models.keys())}",
        )

    if is_model_installed(model_name):
        # Model already installed, return immediately
        async def already_installed():
            yield f"data: {{\"status\": \"completed\", \"percent\": 100, \"model\": \"{model_name}\"}}\n\n"

        return StreamingResponse(
            already_installed(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    async def generate_progress():
        """SSE generator for download progress."""
        progress_queue = asyncio.Queue()
        error_occurred = None

        def progress_callback(percent: int):
            # Put progress in queue for async consumption
            try:
                asyncio.get_event_loop().call_soon_threadsafe(
                    progress_queue.put_nowait, percent
                )
            except Exception:
                pass

        def download_task():
            nonlocal error_occurred
            try:
                download_model(model_name, progress_callback)
            except TranscriptionError as e:
                error_occurred = str(e)
            except Exception as e:
                error_occurred = f"Download failed: {str(e)}"

        # Start download in background thread
        loop = asyncio.get_event_loop()
        download_future = loop.run_in_executor(_executor, download_task)

        # Initial progress
        yield f"data: {{\"status\": \"downloading\", \"percent\": 0, \"model\": \"{model_name}\"}}\n\n"

        last_percent = 0
        completed = False

        while not completed:
            try:
                # Wait for progress update or check if download is done
                try:
                    percent = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    if percent != last_percent:
                        last_percent = percent
                        if percent >= 100:
                            completed = True
                        yield f"data: {{\"status\": \"downloading\", \"percent\": {percent}, \"model\": \"{model_name}\"}}\n\n"
                except asyncio.TimeoutError:
                    # Check if download is done
                    if download_future.done():
                        completed = True
            except Exception:
                completed = True

        # Wait for download to complete
        await download_future

        if error_occurred:
            yield f"data: {{\"status\": \"error\", \"error\": \"{error_occurred}\", \"model\": \"{model_name}\"}}\n\n"
        else:
            yield f"data: {{\"status\": \"completed\", \"percent\": 100, \"model\": \"{model_name}\"}}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
