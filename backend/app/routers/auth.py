import secrets
import logging
from datetime import datetime
from typing import Annotated

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import get_db
from app.dependencies import CurrentUser
from app.models.user import User
from app.schemas.user import UserResponse, TokenResponse
from app.utils.auth import create_access_token
from app.utils.cache import oauth_state_cache

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

# Configure OAuth
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

STATE_EXPIRATION_SECONDS = 600  # 10 minutes


@router.get("/google")
@limiter.limit("10/minute")
async def google_login(request: Request):
    """Redirect to Google OAuth login page."""
    # Generate a random state for CSRF protection with expiration
    state = secrets.token_urlsafe(32)
    oauth_state_cache.set(state, {"created": datetime.utcnow().isoformat()}, ttl_seconds=STATE_EXPIRATION_SECONDS)

    # Build the callback URL (force HTTPS in production - Railway proxy uses HTTP internally)
    base_url = str(request.base_url)
    if settings.environment == "production":
        base_url = base_url.replace("http://", "https://")
    redirect_uri = f"{base_url}auth/google/callback"

    return await oauth.google.authorize_redirect(request, redirect_uri, state=state)


@router.get("/google/callback")
@limiter.limit("10/minute")
async def google_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Handle Google OAuth callback and create/update user."""
    # Verify state exists and is not expired (cache handles expiration)
    state = request.query_params.get("state")
    if not state or not oauth_state_cache.exists(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state"
        )

    # Delete state immediately after validation (one-time use)
    oauth_state_cache.delete(state)

    # Get token from Google
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        # Log the actual error, return generic message
        logger.error(f"Google OAuth error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to authorize with Google"
        )

    # Get user info from Google
    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user info from Google"
        )

    google_id = user_info.get("sub")
    email = user_info.get("email")
    name = user_info.get("name")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required user info"
        )

    # Check if user exists
    result = await db.execute(
        select(User).where(User.google_id == google_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Create new user
        user = User(
            email=email,
            name=name,
            google_id=google_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Update existing user's info
        user.email = email
        user.name = name
        await db.commit()
        await db.refresh(user)

    # Create JWT token
    access_token = create_access_token(user.id, user.email)

    # Redirect to frontend with token in HTTP-only cookie
    frontend_url = settings.frontend_url
    response = RedirectResponse(url=f"{frontend_url}/auth/callback")

    # Set secure cookie with the token
    # Production: SameSite=None + Secure for cross-origin (different domains)
    # Development: SameSite=Lax for same-origin (localhost)
    is_production = settings.environment == "production"
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=settings.jwt_expiration_hours * 3600,
        path="/",
    )

    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser):
    """Get current authenticated user's info."""
    return current_user


@router.post("/logout")
async def logout(response: Response):
    """Logout - clear the auth cookie."""
    is_production = settings.environment == "production"
    response.delete_cookie(
        key="auth_token",
        path="/",
        secure=is_production,
        samesite="none" if is_production else "lax",
    )
    return {"message": "Logged out successfully"}
