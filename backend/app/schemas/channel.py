from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChannelCreate(BaseModel):
    url: str  # YouTube channel URL in any format
    tags: list[str] = []


class ChannelUpdate(BaseModel):
    tags: list[str]


class ChannelResponse(BaseModel):
    id: str
    user_id: str
    youtube_channel_id: str
    youtube_channel_name: Optional[str] = None
    youtube_channel_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    total_videos: Optional[int] = None
    tags: list[str] = []
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    video_count: int = 0

    model_config = {"from_attributes": True}


class ChannelPreview(BaseModel):
    """Preview of channel info before adding."""
    channel_id: str
    channel_name: str
    channel_url: str
    thumbnail_url: Optional[str] = None
    total_videos: Optional[int] = None


class RefreshResult(BaseModel):
    new_videos: int
