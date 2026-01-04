"""
YouTube Data API v3 client for fetching channel and video metadata.
Uses official API for reliability. Transcript extraction still uses yt-dlp.
"""
import re
from typing import Optional
from datetime import datetime

import httpx

from app.config import get_settings
from app.utils.youtube_parser import extract_channel_identifier


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class ChannelInfo:
    def __init__(
        self,
        channel_id: str,
        channel_name: str,
        channel_url: str,
        thumbnail_url: Optional[str] = None,
        subscriber_count: Optional[int] = None,
        description: Optional[str] = None,
        total_videos: Optional[int] = None,
    ):
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.channel_url = channel_url
        self.thumbnail_url = thumbnail_url
        self.subscriber_count = subscriber_count
        self.description = description
        self.total_videos = total_videos


class VideoInfo:
    def __init__(
        self,
        video_id: str,
        title: str,
        description: Optional[str],
        published_at: Optional[datetime],
        duration_seconds: Optional[int],
        thumbnail_url: Optional[str],
        # Engagement stats
        view_count: Optional[int] = None,
        like_count: Optional[int] = None,
        comment_count: Optional[int] = None,
        # Additional metadata
        tags: Optional[list[str]] = None,
        category_id: Optional[str] = None,
        definition: Optional[str] = None,  # hd, sd
        caption: Optional[bool] = None,  # has YouTube captions
        default_language: Optional[str] = None,
        default_audio_language: Optional[str] = None,
    ):
        self.video_id = video_id
        self.title = title
        self.description = description
        self.published_at = published_at
        self.duration_seconds = duration_seconds
        self.thumbnail_url = thumbnail_url
        self.view_count = view_count
        self.like_count = like_count
        self.comment_count = comment_count
        self.tags = tags or []
        self.category_id = category_id
        self.definition = definition
        self.caption = caption
        self.default_language = default_language
        self.default_audio_language = default_audio_language


def _get_api_key() -> str:
    """Get YouTube API key from settings."""
    settings = get_settings()
    if not settings.youtube_api_key:
        raise ValueError("YOUTUBE_API_KEY not configured")
    return settings.youtube_api_key


def _parse_duration(duration: str) -> int:
    """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
    if not duration:
        return 0

    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse ISO date string to datetime object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


def _parse_int(value) -> Optional[int]:
    """Safely parse an integer value."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


async def _resolve_channel_id(identifier: dict, api_key: str) -> Optional[str]:
    """
    Resolve a channel identifier to a channel ID.

    Identifier types:
    - channel: Already a channel ID (UC...)
    - handle: @username
    - custom: /c/customname
    - user: /user/username (legacy)
    """
    id_type = identifier.get('type')
    value = identifier.get('value')

    if id_type == 'channel':
        return value

    async with httpx.AsyncClient() as client:
        if id_type == 'handle':
            # Use forHandle parameter (added in 2022)
            handle = value.lstrip('@')
            resp = await client.get(
                f"{YOUTUBE_API_BASE}/channels",
                params={
                    'forHandle': handle,
                    'part': 'id',
                    'key': api_key,
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])
                if items:
                    return items[0]['id']

        # Fallback: search for the channel
        search_query = value.lstrip('@')
        resp = await client.get(
            f"{YOUTUBE_API_BASE}/search",
            params={
                'q': search_query,
                'type': 'channel',
                'part': 'id',
                'maxResults': 1,
                'key': api_key,
            }
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            if items:
                return items[0]['id']['channelId']

    return None


async def get_channel_info(url: str) -> Optional[ChannelInfo]:
    """
    Get channel information from a YouTube URL using the Data API.

    Args:
        url: YouTube channel URL in any supported format

    Returns:
        ChannelInfo object or None if channel not found
    """
    try:
        api_key = _get_api_key()
    except ValueError:
        return None

    # Parse the URL to get identifier
    identifier = extract_channel_identifier(url)
    if not identifier:
        return None

    # Resolve to channel ID
    channel_id = await _resolve_channel_id(identifier, api_key)
    if not channel_id:
        return None

    # Fetch channel details
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{YOUTUBE_API_BASE}/channels",
            params={
                'id': channel_id,
                'part': 'snippet,statistics,contentDetails',
                'key': api_key,
            }
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        items = data.get('items', [])
        if not items:
            return None

        channel = items[0]
        snippet = channel.get('snippet', {})
        statistics = channel.get('statistics', {})

        # Get best thumbnail
        thumbnails = snippet.get('thumbnails', {})
        thumbnail_url = (
            thumbnails.get('high', {}).get('url') or
            thumbnails.get('medium', {}).get('url') or
            thumbnails.get('default', {}).get('url')
        )

        # Parse subscriber count (may be hidden)
        subscriber_count = None
        if not statistics.get('hiddenSubscriberCount'):
            try:
                subscriber_count = int(statistics.get('subscriberCount', 0))
            except (ValueError, TypeError):
                pass

        # Get total video count
        total_videos = None
        try:
            total_videos = int(statistics.get('videoCount', 0))
        except (ValueError, TypeError):
            pass

        return ChannelInfo(
            channel_id=channel_id,
            channel_name=snippet.get('title', 'Unknown'),
            channel_url=f"https://www.youtube.com/channel/{channel_id}",
            thumbnail_url=thumbnail_url,
            subscriber_count=subscriber_count,
            description=snippet.get('description'),
            total_videos=total_videos,
        )


async def get_channel_videos(channel_id: str, limit: int = 500) -> list[VideoInfo]:
    """
    Get videos from a YouTube channel using the Data API.
    Fetches from the uploads playlist which contains all public videos.

    Args:
        channel_id: YouTube channel ID (UC...)
        limit: Maximum number of videos to fetch (default 500, max ~20000)

    Returns:
        List of VideoInfo objects
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        api_key = _get_api_key()
    except ValueError:
        return []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Get the uploads playlist ID
        resp = await client.get(
            f"{YOUTUBE_API_BASE}/channels",
            params={
                'id': channel_id,
                'part': 'contentDetails,statistics',
                'key': api_key,
            }
        )

        if resp.status_code != 200:
            logger.error(f"Failed to get channel info: {resp.status_code}")
            return []

        data = resp.json()
        items = data.get('items', [])
        if not items:
            return []

        channel_data = items[0]
        uploads_playlist_id = (
            channel_data
            .get('contentDetails', {})
            .get('relatedPlaylists', {})
            .get('uploads')
        )

        # Log total video count from channel stats
        total_videos = channel_data.get('statistics', {}).get('videoCount', 'unknown')
        logger.info(f"Channel {channel_id} has {total_videos} total videos, fetching up to {limit}")

        if not uploads_playlist_id:
            return []

        # Step 2: Get video IDs from playlist (paginated)
        # Note: The uploads playlist contains ALL public videos chronologically
        video_ids = []
        next_page_token = None
        page_count = 0

        while len(video_ids) < limit:
            page_count += 1
            params = {
                'playlistId': uploads_playlist_id,
                'part': 'contentDetails',  # Just need videoId, contentDetails is smaller
                'maxResults': 50,  # Always fetch max per page
                'key': api_key,
            }
            if next_page_token:
                params['pageToken'] = next_page_token

            resp = await client.get(
                f"{YOUTUBE_API_BASE}/playlistItems",
                params=params,
            )

            if resp.status_code != 200:
                logger.error(f"Playlist fetch failed: {resp.status_code} - {resp.text}")
                break

            data = resp.json()

            # Get total results from first page
            if page_count == 1:
                total_in_playlist = data.get('pageInfo', {}).get('totalResults', 0)
                logger.info(f"Playlist {uploads_playlist_id} contains {total_in_playlist} items")

            for item in data.get('items', []):
                video_id = item.get('contentDetails', {}).get('videoId')
                if video_id:
                    video_ids.append(video_id)

            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                logger.info(f"Finished fetching playlist after {page_count} pages, got {len(video_ids)} video IDs")
                break

        if not video_ids:
            return []

        # Step 3: Get full video details (batched by 50)
        videos = []
        missing_count = 0

        for i in range(0, len(video_ids), 50):
            batch_ids = video_ids[i:i + 50]

            resp = await client.get(
                f"{YOUTUBE_API_BASE}/videos",
                params={
                    'id': ','.join(batch_ids),
                    'part': 'snippet,contentDetails,statistics',
                    'key': api_key,
                }
            )

            if resp.status_code != 200:
                logger.error(f"Videos batch fetch failed: {resp.status_code}")
                continue

            data = resp.json()

            # Track missing videos (private/deleted/region-blocked)
            returned_ids = {item['id'] for item in data.get('items', [])}
            for vid in batch_ids:
                if vid not in returned_ids:
                    missing_count += 1
                    logger.debug(f"Video {vid} not accessible (private/deleted/blocked)")

            for item in data.get('items', []):
                snippet = item.get('snippet', {})
                content_details = item.get('contentDetails', {})
                statistics = item.get('statistics', {})

                # Get best thumbnail
                thumbnails = snippet.get('thumbnails', {})
                thumbnail_url = (
                    thumbnails.get('high', {}).get('url') or
                    thumbnails.get('medium', {}).get('url') or
                    thumbnails.get('default', {}).get('url') or
                    f"https://i.ytimg.com/vi/{item['id']}/hqdefault.jpg"
                )

                # Parse engagement stats
                view_count = _parse_int(statistics.get('viewCount'))
                like_count = _parse_int(statistics.get('likeCount'))
                comment_count = _parse_int(statistics.get('commentCount'))

                # Parse caption availability (returns "true" or "false" as string)
                caption_str = content_details.get('caption', 'false')
                has_caption = caption_str.lower() == 'true' if caption_str else None

                videos.append(VideoInfo(
                    video_id=item['id'],
                    title=snippet.get('title', 'Unknown'),
                    description=snippet.get('description'),
                    published_at=_parse_date(snippet.get('publishedAt')),
                    duration_seconds=_parse_duration(content_details.get('duration', '')),
                    thumbnail_url=thumbnail_url,
                    # Engagement stats
                    view_count=view_count,
                    like_count=like_count,
                    comment_count=comment_count,
                    # Additional metadata
                    tags=snippet.get('tags', []),
                    category_id=snippet.get('categoryId'),
                    definition=content_details.get('definition'),  # hd, sd
                    caption=has_caption,
                    default_language=snippet.get('defaultLanguage'),
                    default_audio_language=snippet.get('defaultAudioLanguage'),
                ))

        if missing_count > 0:
            logger.warning(f"Could not fetch {missing_count} videos (private/deleted/blocked)")

        logger.info(f"Successfully fetched {len(videos)} videos from channel {channel_id}")
        return videos
