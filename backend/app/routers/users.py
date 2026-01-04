from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/me")
@limiter.limit("60/minute")
async def get_user_profile(request: Request):
    """Get user profile - to be implemented in Phase 8"""
    return {"message": "Not yet implemented"}


@router.put("/me/telegram")
@limiter.limit("10/minute")
async def update_telegram_config(request: Request):
    """Update Telegram configuration - to be implemented in Phase 8"""
    return {"message": "Not yet implemented"}


@router.post("/me/telegram/test")
@limiter.limit("5/minute")
async def test_telegram(request: Request):
    """Send test Telegram message - to be implemented in Phase 8"""
    return {"message": "Not yet implemented"}
