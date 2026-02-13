"""
Video and transcript management endpoints.
Videos belong to channels, which belong to users.
"""
import asyncio
import json
import re
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import PlainTextResponse, FileResponse, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import yt_dlp

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.channel import Channel
from app.models.video import Video
from app.models.transcript import Transcript
from app.schemas.video import (
    VideoResponse,
    VideoListResponse,
    TranscriptResponse,
    FetchVideosRequest,
    FetchVideosResponse,
)
from app.services.youtube_api import get_channel_videos
from app.services.transcript import extract_transcript, extract_transcript_caption_only, TranscriptionError
from app.services.user_settings import get_cookies_browser
from app.config import get_settings

router = APIRouter()
settings = get_settings()


def _ensure_js_runtime_in_path():
    """Ensure Node.js is in PATH for yt-dlp's n-challenge solver."""
    node_paths = [
        Path.home() / ".local" / "share" / "mise" / "installs" / "node",
        Path.home() / ".nvm" / "versions" / "node",
        Path("/opt/homebrew/opt/node/bin"),
        Path("/usr/local/opt/node/bin"),
    ]

    current_path = os.environ.get("PATH", "")

    for base_path in node_paths:
        if base_path.exists():
            if "mise" in str(base_path) or "nvm" in str(base_path):
                versions = sorted(base_path.iterdir(), reverse=True)
                for version_dir in versions:
                    bin_path = version_dir / "bin"
                    if bin_path.exists() and (bin_path / "node").exists():
                        if str(bin_path) not in current_path:
                            os.environ["PATH"] = f"{bin_path}:{current_path}"
                        return
            else:
                if str(base_path) not in current_path:
                    os.environ["PATH"] = f"{base_path}:{current_path}"
                return


def strip_timestamps(content: str) -> str:
    """Remove timestamps from transcript content."""
    pattern = r'^\[\d{1,2}:\d{2}(?::\d{2})?\]\s*'
    lines = content.split('\n')
    plain_lines = [re.sub(pattern, '', line) for line in lines]
    return '\n'.join(plain_lines)


async def verify_channel_ownership(
    channel_id: str,
    current_user: CurrentUser,
    db: AsyncSession,
) -> Channel:
    """Verify the channel exists and belongs to the current user."""
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.user_id == current_user.id)
    )
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    return channel


@router.get("/channels/{channel_id}/videos", response_model=list[VideoListResponse])
async def list_channel_videos(
    channel_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 500,
    offset: int = 0,
    # Sorting
    sort_by: str = "published_at",  # published_at, view_count, like_count, duration_seconds, title
    sort_order: str = "desc",  # asc, desc
    # Filtering
    transcript_status: Optional[str] = None,  # pending, completed, failed, extracting
    definition: Optional[str] = None,  # hd, sd
    has_caption: Optional[bool] = None,
    search: Optional[str] = None,  # Search in title
):
    """List all videos in a channel with sorting and filtering."""
    channel = await verify_channel_ownership(channel_id, current_user, db)

    query = select(Video).where(Video.channel_id == channel_id)

    # Apply filters
    if transcript_status:
        if transcript_status == "completed":
            query = query.where(Video.has_transcript == True)
        elif transcript_status == "pending":
            query = query.where(Video.has_transcript == False, Video.transcript_status == "pending")
        elif transcript_status == "failed":
            query = query.where(Video.transcript_status == "failed")
        elif transcript_status == "extracting":
            query = query.where(Video.transcript_status == "extracting")

    if definition:
        query = query.where(Video.definition == definition)

    if has_caption is not None:
        query = query.where(Video.caption == has_caption)

    if search:
        # Escape SQL wildcards to prevent injection
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        query = query.where(Video.title.ilike(f"%{safe_search}%", escape="\\"))

    # Apply sorting
    sort_column = {
        "published_at": Video.published_at,
        "view_count": Video.view_count,
        "like_count": Video.like_count,
        "comment_count": Video.comment_count,
        "duration_seconds": Video.duration_seconds,
        "title": Video.title,
    }.get(sort_by, Video.published_at)

    if sort_order == "asc":
        query = query.order_by(sort_column.asc().nullslast())
    else:
        query = query.order_by(sort_column.desc().nullslast())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    video_list = result.scalars().all()

    # Get transcript methods for videos that have transcripts
    video_ids_with_transcripts = [v.id for v in video_list if v.has_transcript]
    transcript_methods = {}
    if video_ids_with_transcripts:
        transcript_result = await db.execute(
            select(Transcript.video_id, Transcript.method)
            .where(Transcript.video_id.in_(video_ids_with_transcripts))
        )
        transcript_methods = {row[0]: row[1] for row in transcript_result.all()}

    videos = []
    for video in video_list:
        videos.append(VideoListResponse(
            id=video.id,
            youtube_video_id=video.youtube_video_id,
            title=video.title,
            published_at=video.published_at,
            duration_seconds=video.duration_seconds,
            thumbnail_url=video.thumbnail_url,
            # Engagement stats
            view_count=video.view_count,
            like_count=video.like_count,
            comment_count=video.comment_count,
            # Metadata
            definition=video.definition,
            caption=video.caption,
            # Transcript status
            has_transcript=video.has_transcript,
            transcript_status=video.transcript_status or "pending",
            transcript_method=transcript_methods.get(video.id),
            transcript_error=video.transcript_error,
            channel_name=channel.youtube_channel_name,
        ))

    return videos


@router.get("/videos/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get video details."""
    result = await db.execute(
        select(Video, Channel)
        .join(Channel, Video.channel_id == Channel.id)
        .where(Video.id == video_id, Channel.user_id == current_user.id)
    )

    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    video, channel = row
    return VideoResponse(
        id=video.id,
        channel_id=video.channel_id,
        youtube_video_id=video.youtube_video_id,
        title=video.title,
        description=video.description,
        published_at=video.published_at,
        duration_seconds=video.duration_seconds,
        thumbnail_url=video.thumbnail_url,
        # Engagement stats
        view_count=video.view_count,
        like_count=video.like_count,
        comment_count=video.comment_count,
        # Additional metadata
        tags=video.tags_list,
        category_id=video.category_id,
        definition=video.definition,
        caption=video.caption,
        default_language=video.default_language,
        default_audio_language=video.default_audio_language,
        # Transcript status
        has_transcript=video.has_transcript,
        transcript_status=video.transcript_status or "pending",
        created_at=video.created_at,
        channel_name=channel.youtube_channel_name,
    )


@router.get("/videos/{video_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    video_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get transcript for a video."""
    # Verify ownership
    result = await db.execute(
        select(Video)
        .join(Channel, Video.channel_id == Channel.id)
        .where(Video.id == video_id, Channel.user_id == current_user.id)
    )

    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    # Get transcript
    result = await db.execute(
        select(Transcript).where(Transcript.video_id == video_id)
    )
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not available for this video"
        )

    return TranscriptResponse(
        id=transcript.id,
        video_id=transcript.video_id,
        content=transcript.content,
        plain_content=strip_timestamps(transcript.content),
        language=transcript.language,
        word_count=transcript.word_count,
        method=transcript.method or "caption",
        created_at=transcript.created_at,
    )


@router.get("/videos/{video_id}/transcript/download")
async def download_transcript(
    video_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Download transcript as a text file."""
    # Verify ownership and get video info
    result = await db.execute(
        select(Video, Channel.youtube_channel_name)
        .join(Channel, Video.channel_id == Channel.id)
        .where(Video.id == video_id, Channel.user_id == current_user.id)
    )

    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    video, channel_name = row

    # Get transcript
    result = await db.execute(
        select(Transcript).where(Transcript.video_id == video_id)
    )
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not available for this video"
        )

    # Build downloadable content
    content = f"""Title: {video.title}
Channel: {channel_name}
Video URL: https://www.youtube.com/watch?v={video.youtube_video_id}
Word Count: {transcript.word_count}
Language: {transcript.language}

---

{transcript.content}
"""

    # Clean filename
    safe_title = "".join(c for c in video.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"{safe_title[:50]}_transcript.txt"

    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/videos/{video_id}/download-audio")
@limiter.limit("10/minute")
async def download_audio(
    request: Request,
    video_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """Download audio from a YouTube video for local transcription."""
    import shutil
    _ensure_js_runtime_in_path()

    # Verify ownership and get video info
    result = await db.execute(
        select(Video, Channel.youtube_channel_name)
        .join(Channel, Video.channel_id == Channel.id)
        .where(Video.id == video_id, Channel.user_id == current_user.id)
    )

    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    video, channel_name = row
    youtube_video_id = video.youtube_video_id

    # Create temp directory for download
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, f"{youtube_video_id}.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio/best',  # Flexible: any audio stream, or best overall if no separate audio
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '64',
        }],
        'cookiesfrombrowser': (get_cookies_browser(),),
        'js_runtimes': {'node': {}},  # Enable Node.js for YouTube n-challenge
    }

    # Add proxy if configured
    if settings.proxy_url:
        ydl_opts['proxy'] = settings.proxy_url

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={youtube_video_id}"])

        # Find the downloaded file
        audio_path = os.path.join(temp_dir, f"{youtube_video_id}.mp3")
        if not os.path.exists(audio_path):
            # Check for other formats
            for ext in ['m4a', 'wav', 'webm', 'ogg']:
                path = os.path.join(temp_dir, f"{youtube_video_id}.{ext}")
                if os.path.exists(path):
                    audio_path = path
                    break

        if not os.path.exists(audio_path):
            # Cleanup on failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to download audio"
            )

        # Clean filename for download: YYYYMMDD_title.mp3
        date_prefix = ""
        if video.published_at:
            date_prefix = video.published_at.strftime("%Y%m%d") + "_"
        safe_title = re.sub(r'[<>:"/\\|?*]', '', video.title).strip()[:80]
        filename = f"{date_prefix}{safe_title}.mp3"

        # Schedule cleanup after file is sent
        def cleanup_temp():
            import time
            time.sleep(30)  # Wait for file to be fully sent
            shutil.rmtree(temp_dir, ignore_errors=True)

        background_tasks.add_task(cleanup_temp)

        return FileResponse(
            path=audio_path,
            filename=filename,
            media_type="audio/mpeg",
        )

    except yt_dlp.utils.DownloadError as e:
        # Cleanup on exception
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download audio: {str(e)[:100]}"
        )


@router.post("/videos/{video_id}/extract-transcript", response_model=VideoResponse)
@limiter.limit("20/minute")
async def extract_video_transcript(
    request: Request,
    video_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    use_ai: bool = True,  # If True, fall back to AI when no captions available
    provider: Optional[str] = None,  # AI provider: "replicate" or "siliconflow"
):
    """Extract transcript for a video."""
    # Verify ownership
    result = await db.execute(
        select(Video, Channel)
        .join(Channel, Video.channel_id == Channel.id)
        .where(Video.id == video_id, Channel.user_id == current_user.id)
    )

    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    video, channel = row

    # Check if already has transcript
    if video.has_transcript:
        return VideoResponse(
            id=video.id,
            channel_id=video.channel_id,
            youtube_video_id=video.youtube_video_id,
            title=video.title,
            description=video.description,
            published_at=video.published_at,
            duration_seconds=video.duration_seconds,
            thumbnail_url=video.thumbnail_url,
            view_count=video.view_count,
            like_count=video.like_count,
            comment_count=video.comment_count,
            tags=video.tags_list,
            category_id=video.category_id,
            definition=video.definition,
            caption=video.caption,
            default_language=video.default_language,
            default_audio_language=video.default_audio_language,
            has_transcript=video.has_transcript,
            transcript_status=video.transcript_status or "completed",
            created_at=video.created_at,
            channel_name=channel.youtube_channel_name,
        )

    # Update status to extracting
    video.transcript_status = "extracting"
    video.transcript_error = None  # Clear previous error
    await db.commit()

    # Extract transcript
    transcript_method = None
    try:
        if use_ai:
            transcript_result = await extract_transcript(video.youtube_video_id, provider=provider)
        else:
            transcript_result = await extract_transcript_caption_only(video.youtube_video_id)

        if transcript_result:
            # Create transcript record
            transcript = Transcript(
                video_id=video.id,
                content=transcript_result.content,
                language=transcript_result.language,
                word_count=transcript_result.word_count,
                method=transcript_result.method,
            )
            db.add(transcript)

            video.has_transcript = True
            video.transcript_status = "completed"
            video.transcript_error = None
            transcript_method = transcript_result.method
        else:
            video.transcript_status = "failed"
            video.transcript_error = "No transcript available"
    except TranscriptionError as e:
        video.transcript_status = "failed"
        video.transcript_error = str(e)
    except Exception as e:
        # Catch any unexpected errors to prevent stuck "extracting" status
        video.transcript_status = "failed"
        video.transcript_error = f"Unexpected error: {str(e)[:200]}"

    await db.commit()
    await db.refresh(video)

    return VideoResponse(
        id=video.id,
        channel_id=video.channel_id,
        youtube_video_id=video.youtube_video_id,
        title=video.title,
        description=video.description,
        published_at=video.published_at,
        duration_seconds=video.duration_seconds,
        thumbnail_url=video.thumbnail_url,
        view_count=video.view_count,
        like_count=video.like_count,
        comment_count=video.comment_count,
        tags=video.tags_list,
        category_id=video.category_id,
        definition=video.definition,
        caption=video.caption,
        default_language=video.default_language,
        default_audio_language=video.default_audio_language,
        has_transcript=video.has_transcript,
        transcript_status=video.transcript_status,
        transcript_method=transcript_method,
        transcript_error=video.transcript_error,
        created_at=video.created_at,
        channel_name=channel.youtube_channel_name,
    )


@router.post("/channels/{channel_id}/fetch-videos", response_model=FetchVideosResponse)
async def fetch_channel_videos(
    channel_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: FetchVideosRequest = FetchVideosRequest(),
):
    """Fetch latest videos from a YouTube channel."""
    channel = await verify_channel_ownership(channel_id, current_user, db)

    # Fetch videos from YouTube using channel ID
    video_infos = await get_channel_videos(channel.youtube_channel_id, limit=request.limit)

    # Get existing video IDs (check globally since youtube_video_id has a unique constraint)
    existing_result = await db.execute(
        select(Video.youtube_video_id).where(
            Video.youtube_video_id.in_([info.video_id for info in video_infos])
        )
    )
    existing_ids = {row[0] for row in existing_result.all()}

    # Add new videos
    new_count = 0
    for info in video_infos:
        if info.video_id not in existing_ids:
            video = Video(
                channel_id=channel_id,
                youtube_video_id=info.video_id,
                title=info.title,
                description=info.description,
                published_at=info.published_at,
                duration_seconds=info.duration_seconds,
                thumbnail_url=info.thumbnail_url,
                # Engagement stats
                view_count=info.view_count,
                like_count=info.like_count,
                comment_count=info.comment_count,
                # Additional metadata
                tags=json.dumps(info.tags or []),
                category_id=info.category_id,
                definition=info.definition,
                caption=info.caption,
                default_language=info.default_language,
                default_audio_language=info.default_audio_language,
            )
            db.add(video)
            new_count += 1

    # Update channel's last_checked_at
    channel.last_checked_at = datetime.utcnow()

    await db.commit()

    # Get total video count
    count_result = await db.execute(
        select(func.count(Video.id)).where(Video.channel_id == channel_id)
    )
    total_count = count_result.scalar()

    return FetchVideosResponse(
        new_videos=new_count,
        total_videos=total_count or 0,
    )


from app.utils.cache import download_token_cache

# Download token TTL: 10 minutes
DOWNLOAD_TOKEN_TTL = 600


@router.get("/channels/{channel_id}/prepare-all-audio")
async def prepare_all_audio(
    channel_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    video_ids: Optional[str] = None,  # Comma-separated video IDs
):
    """
    Prepare audio for videos as a ZIP file.
    If video_ids provided, downloads those specific videos.
    Otherwise downloads all pending videos (without transcripts).
    Streams progress updates via SSE, then returns download token.
    """
    import zipfile
    import shutil
    import json
    import asyncio

    channel = await verify_channel_ownership(channel_id, current_user, db)

    # Get videos based on selection or all pending
    if video_ids:
        # Parse comma-separated UUIDs
        try:
            selected_ids = [vid.strip() for vid in video_ids.split(',') if vid.strip()]
        except ValueError:
            async def error_stream():
                yield f"data: {json.dumps({'error': 'Invalid video IDs'})}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")

        result = await db.execute(
            select(Video).where(
                Video.channel_id == channel_id,
                Video.id.in_(selected_ids),
            ).order_by(Video.published_at.desc().nullslast())
        )
    else:
        # All pending videos (no transcript)
        result = await db.execute(
            select(Video).where(
                Video.channel_id == channel_id,
                Video.has_transcript == False,
            ).order_by(Video.published_at.desc().nullslast())
        )

    videos = list(result.scalars().all())
    total = len(videos)

    if total == 0:
        async def empty_stream():
            yield f"data: {json.dumps({'error': 'No pending videos to download'})}\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    async def generate_progress():
        _ensure_js_runtime_in_path()
        temp_dir = tempfile.mkdtemp()
        audio_files = []
        completed = 0
        failed = 0

        try:
            for video in videos:
                # Send progress update
                yield f"data: {json.dumps({'status': 'downloading', 'current': completed + 1, 'total': total, 'title': video.title[:50]})}\n\n"

                youtube_video_id = video.youtube_video_id
                output_template = os.path.join(temp_dir, f"{youtube_video_id}.%(ext)s")

                ydl_opts = {
                    'format': 'bestaudio/best',  # Flexible: any audio stream, or best overall if no separate audio
                    'outtmpl': output_template,
                    'quiet': True,
                    'no_warnings': True,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '64',
                    }],
                    'cookiesfrombrowser': (get_cookies_browser(),),
                    'js_runtimes': {'node': {}},  # Enable Node.js for YouTube n-challenge
                }

                # Add proxy if configured
                if settings.proxy_url:
                    ydl_opts['proxy'] = settings.proxy_url

                try:
                    # Run yt-dlp in thread pool to not block
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([f"https://www.youtube.com/watch?v={youtube_video_id}"]))

                    # Find the downloaded file
                    audio_path = os.path.join(temp_dir, f"{youtube_video_id}.mp3")
                    if not os.path.exists(audio_path):
                        for ext in ['m4a', 'wav', 'webm', 'ogg']:
                            path = os.path.join(temp_dir, f"{youtube_video_id}.{ext}")
                            if os.path.exists(path):
                                audio_path = path
                                break

                    if os.path.exists(audio_path):
                        # Format: YYYYMMDD_title.ext
                        date_prefix = ""
                        if video.published_at:
                            date_prefix = video.published_at.strftime("%Y%m%d") + "_"
                        safe_title = re.sub(r'[<>:"/\\|?*]', '', video.title).strip()[:80]
                        ext = os.path.splitext(audio_path)[1]
                        audio_files.append((audio_path, f"{date_prefix}{safe_title}{ext}"))
                        completed += 1
                    else:
                        failed += 1

                except Exception:
                    failed += 1
                    continue

            if not audio_files:
                yield f"data: {json.dumps({'error': 'Failed to download any audio files'})}\n\n"
                shutil.rmtree(temp_dir, ignore_errors=True)
                return

            # Send zipping status
            yield f"data: {json.dumps({'status': 'zipping', 'completed': completed, 'failed': failed})}\n\n"

            # Create ZIP file
            zip_path = os.path.join(temp_dir, "audio_files.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for audio_path, filename in audio_files:
                    zf.write(audio_path, filename)

            # Generate download token and store path with user ownership
            import uuid as uuid_mod
            token = str(uuid_mod.uuid4())
            safe_channel = re.sub(r'[<>:"/\\|?*]', '', channel.youtube_channel_name).strip()[:50]
            download_token_cache.set(token, {
                'path': zip_path,
                'filename': f"{safe_channel}_audio.zip",
                'temp_dir': temp_dir,
                'user_id': str(current_user.id),
            }, ttl_seconds=DOWNLOAD_TOKEN_TTL)

            # Send completion with download token
            yield f"data: {json.dumps({'status': 'ready', 'token': token, 'completed': completed, 'failed': failed})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            shutil.rmtree(temp_dir, ignore_errors=True)

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/download-prepared-audio/{token}")
async def download_prepared_audio(token: str, current_user: CurrentUser, background_tasks: BackgroundTasks):
    """Download a prepared ZIP file using the token from prepare-all-audio."""
    import shutil

    zip_info = download_token_cache.get(token)
    if not zip_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found or expired"
        )

    # Verify user ownership
    if zip_info.get('user_id') != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Remove token from cache (one-time use)
    download_token_cache.delete(token)

    # Schedule cleanup using FastAPI background tasks (runs after response)
    def cleanup_temp_dir():
        import time
        time.sleep(30)  # Wait for file to be fully sent
        shutil.rmtree(zip_info['temp_dir'], ignore_errors=True)

    background_tasks.add_task(cleanup_temp_dir)

    return FileResponse(
        path=zip_info['path'],
        filename=zip_info['filename'],
        media_type="application/zip",
    )


@router.get("/channels/{channel_id}/extract-transcripts-stream")
async def extract_transcripts_stream(
    channel_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    use_ai: bool = False,
    video_ids: Optional[str] = None,
):
    """
    Extract transcripts with streaming progress via SSE.
    """
    import json

    channel = await verify_channel_ownership(channel_id, current_user, db)

    # Get videos to process
    query = select(Video).where(
        Video.channel_id == channel_id,
        Video.has_transcript == False,
        Video.transcript_status != "extracting",
    )

    if video_ids:
        try:
            selected_ids = [vid.strip() for vid in video_ids.split(',') if vid.strip()]
            query = query.where(Video.id.in_(selected_ids))
        except ValueError:
            pass

    if not use_ai and not video_ids:
        query = query.where(Video.caption == True)

    query = query.order_by(Video.published_at.desc().nullslast())
    result = await db.execute(query)
    videos = list(result.scalars().all())
    total = len(videos)

    if total == 0:
        async def empty_stream():
            yield f"data: {json.dumps({'status': 'complete', 'extracted': 0, 'extracted_ai': 0, 'failed': 0, 'total': 0})}\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    async def generate_progress():
        extracted = 0
        extracted_ai = 0
        failed = 0

        for i, video in enumerate(videos):
            # Send progress update
            yield f"data: {json.dumps({'status': 'extracting', 'current': i + 1, 'total': total, 'title': video.title[:50], 'extracted': extracted, 'extracted_ai': extracted_ai, 'failed': failed})}\n\n"

            if video.has_transcript:
                continue

            video.transcript_status = "extracting"
            await db.commit()

            try:
                if use_ai:
                    transcript_result = await extract_transcript(video.youtube_video_id)
                else:
                    transcript_result = await extract_transcript_caption_only(video.youtube_video_id)

                if transcript_result:
                    transcript = Transcript(
                        video_id=video.id,
                        content=transcript_result.content,
                        language=transcript_result.language,
                        word_count=transcript_result.word_count,
                        method=transcript_result.method,
                    )
                    db.add(transcript)
                    video.has_transcript = True
                    video.transcript_status = "completed"
                    if transcript_result.method in ("ai", "whisper-mlx", "whisper-faster-whisper"):
                        extracted_ai += 1
                    else:
                        extracted += 1
                else:
                    video.transcript_status = "failed"
                    video.transcript_error = "No transcript available"
                    failed += 1
            except Exception as e:
                video.transcript_status = "failed"
                video.transcript_error = str(e)[:200]
                failed += 1

            await db.commit()

        # Send completion
        yield f"data: {json.dumps({'status': 'complete', 'extracted': extracted, 'extracted_ai': extracted_ai, 'failed': failed, 'total': total})}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/channels/{channel_id}/export-markdown")
async def export_markdown(
    channel_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    video_ids: Optional[str] = None,  # Comma-separated video IDs; if omitted, exports all extracted
):
    """Export video details and transcripts as a single Markdown file."""
    channel = await verify_channel_ownership(channel_id, current_user, db)

    # Build query for videos with transcripts
    query = (
        select(Video, Transcript)
        .join(Transcript, Transcript.video_id == Video.id)
        .where(Video.channel_id == channel_id, Video.has_transcript == True)
    )

    if video_ids:
        selected_ids = [vid.strip() for vid in video_ids.split(",") if vid.strip()]
        if selected_ids:
            query = query.where(Video.id.in_(selected_ids))

    query = query.order_by(Video.published_at.asc().nullslast())
    result = await db.execute(query)
    rows = result.all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No transcripts found to export",
        )

    # Build markdown
    parts: list[str] = []
    parts.append(f"# {channel.youtube_channel_name}\n")
    parts.append(f"Exported {len(rows)} video{'s' if len(rows) != 1 else ''} with transcripts.\n")
    parts.append("---\n")

    for video, transcript in rows:
        parts.append(f"## {video.title}\n")

        # Metadata table
        meta_lines = []
        if video.published_at:
            meta_lines.append(f"- **Published**: {video.published_at.strftime('%Y-%m-%d')}")
        meta_lines.append(f"- **URL**: https://www.youtube.com/watch?v={video.youtube_video_id}")
        if video.duration_seconds:
            h, rem = divmod(video.duration_seconds, 3600)
            m, s = divmod(rem, 60)
            dur = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
            meta_lines.append(f"- **Duration**: {dur}")
        if video.view_count is not None:
            meta_lines.append(f"- **Views**: {video.view_count:,}")
        if video.like_count is not None:
            meta_lines.append(f"- **Likes**: {video.like_count:,}")
        meta_lines.append(f"- **Words**: {transcript.word_count:,}")
        meta_lines.append(f"- **Language**: {transcript.language}")
        meta_lines.append(f"- **Method**: {transcript.method or 'caption'}")
        parts.append("\n".join(meta_lines))
        parts.append("")

        # Transcript content
        plain = strip_timestamps(transcript.content)
        parts.append("### Transcript\n")
        parts.append(plain)
        parts.append("\n---\n")

    content = "\n".join(parts)

    # Filename
    safe_channel = re.sub(r'[<>:"/\\|?*]', "", channel.youtube_channel_name).strip()[:50]
    filename = f"{safe_channel}_transcripts.md"

    return PlainTextResponse(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/channels/{channel_id}/extract-all-transcripts")
async def extract_all_channel_transcripts(
    channel_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    use_ai: bool = False,  # If True, use AI for videos without captions
    provider: Optional[str] = None,  # AI provider: "replicate" or "siliconflow"
    video_ids: Optional[str] = None,  # Comma-separated video IDs to extract (if not provided, extracts all)
):
    """
    Extract transcripts for videos in a channel (non-streaming version).
    """
    await verify_channel_ownership(channel_id, current_user, db)

    # Get videos to process
    query = select(Video).where(
        Video.channel_id == channel_id,
        Video.has_transcript == False,
        Video.transcript_status != "extracting",
    )

    # If specific video IDs provided, filter to those
    if video_ids:
        try:
            selected_ids = [vid.strip() for vid in video_ids.split(',') if vid.strip()]
            query = query.where(Video.id.in_(selected_ids))
        except ValueError:
            pass  # Invalid UUIDs, just process all

    # If not using AI, only get videos with captions (unless specific videos selected)
    if not use_ai and not video_ids:
        query = query.where(Video.caption == True)

    query = query.order_by(Video.published_at.desc().nullslast())
    result = await db.execute(query)
    videos = result.scalars().all()

    extracted = 0
    extracted_ai = 0
    already_completed = 0
    failed = 0

    for video in videos:
        if video.has_transcript:
            already_completed += 1
            continue

        # Update status to extracting
        video.transcript_status = "extracting"
        await db.commit()

        try:
            # Extract transcript (use AI fallback only if use_ai is True)
            if use_ai:
                transcript_result = await extract_transcript(video.youtube_video_id, provider=provider)
            else:
                transcript_result = await extract_transcript_caption_only(video.youtube_video_id)

            if transcript_result:
                transcript = Transcript(
                    video_id=video.id,
                    content=transcript_result.content,
                    language=transcript_result.language,
                    word_count=transcript_result.word_count,
                    method=transcript_result.method,
                )
                db.add(transcript)
                video.has_transcript = True
                video.transcript_status = "completed"
                if transcript_result.method in ("ai", "whisper-mlx", "whisper-faster-whisper"):
                    extracted_ai += 1
                else:
                    extracted += 1
            else:
                video.transcript_status = "failed"
                failed += 1
        except Exception as e:
            video.transcript_status = "failed"
            video.transcript_error = str(e)[:200]
            failed += 1

        await db.commit()

    return {
        "extracted": extracted,
        "extracted_ai": extracted_ai,
        "already_completed": already_completed,
        "failed": failed,
        "total_processed": len(videos),
    }
