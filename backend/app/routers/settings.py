"""
User settings endpoints for runtime configuration.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.user_settings import (
    get_all_settings,
    get_cookies_browser,
    set_cookies_browser,
    get_valid_browsers,
    get_whisper_model,
)

router = APIRouter()


class SettingsResponse(BaseModel):
    cookies_from_browser: str
    valid_browsers: list[str]
    whisper_model: str


class UpdateBrowserRequest(BaseModel):
    browser: str


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current user settings."""
    return SettingsResponse(
        cookies_from_browser=get_cookies_browser(),
        valid_browsers=get_valid_browsers(),
        whisper_model=get_whisper_model(),
    )


@router.put("/settings/browser")
async def update_browser(request: UpdateBrowserRequest):
    """Update the browser used for cookie extraction."""
    if not set_cookies_browser(request.browser):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid browser. Valid options: {', '.join(get_valid_browsers())}",
        )
    return {"success": True, "browser": request.browser}
