"""
Channel management endpoints.
Channels belong directly to users (no spaces).
"""
import os
import re
import tempfile
import zipfile
from typing import Annotated, Optional

import yt_dlp
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import FileResponse
import json
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db

limiter = Limiter(key_func=get_remote_address)
from app.dependencies import CurrentUser
from app.models.channel import Channel
from app.models.video import Video
from app.schemas.channel import ChannelCreate, ChannelUpdate, ChannelResponse, ChannelPreview
from app.services.youtube_api import get_channel_info

router = APIRouter()


@router.get("/channels", response_model=list[ChannelResponse])
@limiter.limit("60/minute")
async def list_channels(
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    tag: Optional[str] = Query(None, description="Filter by tag"),
):
    """List all channels for current user, optionally filtered by tag."""
    query = (
        select(
            Channel,
            func.count(Video.id).label("video_count"),
        )
        .outerjoin(Video, Channel.id == Video.channel_id)
        .where(Channel.user_id == current_user.id)
    )

    if tag:
        # SQLite: tags stored as JSON string, use LIKE for filtering
        query = query.where(Channel.tags.like(f'%"{tag}"%'))

    query = query.group_by(Channel.id).order_by(Channel.created_at.desc())

    result = await db.execute(query)

    channels = []
    for row in result.all():
        channel = row[0]
        channels.append(ChannelResponse(
            id=channel.id,
            user_id=channel.user_id,
            youtube_channel_id=channel.youtube_channel_id,
            youtube_channel_name=channel.youtube_channel_name,
            youtube_channel_url=channel.youtube_channel_url,
            thumbnail_url=channel.thumbnail_url,
            total_videos=channel.total_videos,
            tags=channel.tags_list,
            last_checked_at=channel.last_checked_at,
            created_at=channel.created_at,
            video_count=row[1],
        ))

    return channels


@router.post("/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def add_channel(
    request: Request,
    channel_data: ChannelCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add a YouTube channel."""
    # Get channel info from YouTube
    channel_info = await get_channel_info(channel_data.url)
    if not channel_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not find YouTube channel. Please check the URL."
        )

    # Check if channel already exists for this user
    existing = await db.execute(
        select(Channel).where(
            Channel.user_id == current_user.id,
            Channel.youtube_channel_id == channel_info.channel_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already added this channel"
        )

    # Create channel
    channel = Channel(
        user_id=current_user.id,
        youtube_channel_id=channel_info.channel_id,
        youtube_channel_name=channel_info.channel_name,
        youtube_channel_url=channel_info.channel_url,
        thumbnail_url=channel_info.thumbnail_url,
        total_videos=channel_info.total_videos,
        tags=json.dumps(channel_data.tags),
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)

    return ChannelResponse(
        id=channel.id,
        user_id=channel.user_id,
        youtube_channel_id=channel.youtube_channel_id,
        youtube_channel_name=channel.youtube_channel_name,
        youtube_channel_url=channel.youtube_channel_url,
        thumbnail_url=channel.thumbnail_url,
        total_videos=channel.total_videos,
        tags=channel.tags_list,
        last_checked_at=channel.last_checked_at,
        created_at=channel.created_at,
        video_count=0,
    )


@router.get("/channels/preview", response_model=ChannelPreview)
@limiter.limit("20/minute")
async def preview_channel(
    request: Request,
    url: str,
    current_user: CurrentUser,
):
    """Preview channel info before adding (validates URL and shows channel details)."""
    channel_info = await get_channel_info(url)
    if not channel_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not find YouTube channel. Please check the URL."
        )

    return ChannelPreview(
        channel_id=channel_info.channel_id,
        channel_name=channel_info.channel_name,
        channel_url=channel_info.channel_url,
        thumbnail_url=channel_info.thumbnail_url,
        total_videos=channel_info.total_videos,
    )


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
@limiter.limit("60/minute")
async def get_channel(
    request: Request,
    channel_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get channel details."""
    result = await db.execute(
        select(
            Channel,
            func.count(Video.id).label("video_count"),
        )
        .outerjoin(Video, Channel.id == Video.channel_id)
        .where(Channel.id == channel_id, Channel.user_id == current_user.id)
        .group_by(Channel.id)
    )

    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    channel = row[0]
    return ChannelResponse(
        id=channel.id,
        user_id=channel.user_id,
        youtube_channel_id=channel.youtube_channel_id,
        youtube_channel_name=channel.youtube_channel_name,
        youtube_channel_url=channel.youtube_channel_url,
        thumbnail_url=channel.thumbnail_url,
        total_videos=channel.total_videos,
        tags=channel.tags_list,
        last_checked_at=channel.last_checked_at,
        created_at=channel.created_at,
        video_count=row[1],
    )


@router.put("/channels/{channel_id}", response_model=ChannelResponse)
@limiter.limit("30/minute")
async def update_channel(
    request: Request,
    channel_id: str,
    channel_data: ChannelUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update channel tags."""
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.user_id == current_user.id)
    )
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    channel.tags = json.dumps(channel_data.tags)
    await db.commit()
    await db.refresh(channel)

    # Get video count
    count_result = await db.execute(
        select(func.count(Video.id)).where(Video.channel_id == channel_id)
    )
    video_count = count_result.scalar() or 0

    return ChannelResponse(
        id=channel.id,
        user_id=channel.user_id,
        youtube_channel_id=channel.youtube_channel_id,
        youtube_channel_name=channel.youtube_channel_name,
        youtube_channel_url=channel.youtube_channel_url,
        thumbnail_url=channel.thumbnail_url,
        total_videos=channel.total_videos,
        tags=channel.tags_list,
        last_checked_at=channel.last_checked_at,
        created_at=channel.created_at,
        video_count=video_count,
    )


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def remove_channel(
    request: Request,
    channel_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove a channel (also deletes all its videos and transcripts)."""
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.user_id == current_user.id)
    )
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    await db.delete(channel)
    await db.commit()

    return None


@router.get("/channels/tags/all", response_model=list[str])
@limiter.limit("60/minute")
async def list_all_tags(
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get all unique tags used by the current user's channels."""
    result = await db.execute(
        select(Channel.tags).where(Channel.user_id == current_user.id)
    )

    all_tags = set()
    for row in result.all():
        if row[0]:
            # Tags stored as JSON string
            tags = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            all_tags.update(tags)

    return sorted(list(all_tags))
