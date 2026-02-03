from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import get_settings
from app.database import engine, Base
from app.routers import channels, videos, users, settings as settings_router, whisper
# Import models to register them with Base
from app.models import user, channel, video, transcript  # noqa: F401

settings = get_settings()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # start_scheduler()  # Will be enabled in Phase 6
    yield
    # Shutdown
    # shutdown_scheduler()  # Will be enabled in Phase 6


app = FastAPI(title="Scribr API", version="1.0.0", lifespan=lifespan)

# Rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - explicitly list allowed methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Routers
app.include_router(channels.router, tags=["channels"])
app.include_router(videos.router, tags=["videos"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(settings_router.router, tags=["settings"])
app.include_router(whisper.router, tags=["whisper"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
