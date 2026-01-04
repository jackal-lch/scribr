from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class VideoResponse(BaseModel):
    id: UUID
    channel_id: UUID
    youtube_video_id: str
    title: str
    description: Optional[str] = None
    published_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    thumbnail_url: Optional[str] = None

    # Engagement stats
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None

    # Additional metadata
    tags: list[str] = []
    category_id: Optional[str] = None
    definition: Optional[str] = None  # hd, sd
    caption: Optional[bool] = None  # has YouTube captions
    default_language: Optional[str] = None
    default_audio_language: Optional[str] = None

    # Transcript status
    has_transcript: bool = False
    transcript_status: str = "pending"  # pending, extracting, completed, failed
    transcript_method: Optional[str] = None  # "caption" or "ai"
    transcript_error: Optional[str] = None  # Error message if failed
    created_at: datetime

    # Include channel info for display
    channel_name: Optional[str] = None

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    """Lighter response for video lists."""
    id: UUID
    youtube_video_id: str
    title: str
    published_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    thumbnail_url: Optional[str] = None

    # Engagement stats
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None

    # Key metadata
    definition: Optional[str] = None
    caption: Optional[bool] = None

    # Transcript status
    has_transcript: bool = False
    transcript_status: str = "pending"
    transcript_method: Optional[str] = None  # "caption" or "ai"
    transcript_error: Optional[str] = None  # Error message if failed
    channel_name: Optional[str] = None

    model_config = {"from_attributes": True}


class TranscriptResponse(BaseModel):
    id: UUID
    video_id: UUID
    content: str  # Timestamped version
    plain_content: str  # Plain version without timestamps
    language: str
    word_count: int
    method: str = "caption"  # "caption" or "ai"
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptDownload(BaseModel):
    """Format for downloading transcript."""
    video_title: str
    channel_name: str
    content: str
    word_count: int


class FetchVideosRequest(BaseModel):
    """Request to fetch videos from a channel."""
    limit: int = 500  # Fetch up to 500 videos by default


class FetchVideosResponse(BaseModel):
    """Response after fetching videos."""
    new_videos: int
    total_videos: int
