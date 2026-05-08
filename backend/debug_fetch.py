#!/usr/bin/env python3
"""
Debug script to test YouTube video fetching.
Usage: python debug_fetch.py <channel_url_or_id>
"""
import asyncio
import sys
from app.services.youtube_api import get_channel_info, get_channel_videos
from app.config import get_settings

async def debug_fetch(channel_url: str):
    """Debug video fetching for a channel."""
    print(f"🔍 Debugging video fetch for: {channel_url}\n")

    # Check API key
    settings = get_settings()
    if not settings.youtube_api_key:
        print("❌ ERROR: YOUTUBE_API_KEY not configured in .env")
        return

    print("✅ YouTube API key is configured\n")

    # Get channel info
    print("📺 Fetching channel info...")
    channel_info = await get_channel_info(channel_url)

    if not channel_info:
        print("❌ ERROR: Could not fetch channel info")
        print("   - Check if the URL is correct")
        print("   - Check if your API key is valid")
        print("   - Check your internet connection")
        return

    print(f"✅ Channel: {channel_info.channel_name}")
    print(f"   ID: {channel_info.channel_id}")
    print(f"   Total videos (from API): {channel_info.total_videos}")
    print()

    # Fetch videos with small limit first
    print("📹 Fetching first 10 videos...")
    videos_small = await get_channel_videos(channel_info.channel_id, limit=10)

    if not videos_small:
        print("❌ ERROR: Could not fetch any videos")
        print("   - The channel might not have any public videos")
        print("   - API quota might be exhausted")
        return

    print(f"✅ Fetched {len(videos_small)} videos\n")
    print("📋 Most recent videos:")
    for i, video in enumerate(videos_small[:5], 1):
        print(f"   {i}. {video.title[:60]}")
        print(f"      Video ID: {video.video_id}")
        print(f"      Published: {video.published_at}")
        print()

    # Now fetch with default limit (500)
    print(f"📹 Fetching up to 500 videos...")
    videos_full = await get_channel_videos(channel_info.channel_id, limit=500)
    print(f"✅ Fetched {len(videos_full)} videos\n")

    # Analysis
    print("📊 Analysis:")
    print(f"   - Channel claims to have {channel_info.total_videos} total videos")
    print(f"   - We fetched {len(videos_full)} videos")
    if channel_info.total_videos and len(videos_full) < channel_info.total_videos:
        missing = channel_info.total_videos - len(videos_full)
        print(f"   - ⚠️  Missing {missing} videos (might be private/unlisted)")

    # Check for recent videos
    if videos_small:
        latest = videos_small[0]
        print(f"\n🕐 Most recent video:")
        print(f"   Title: {latest.title}")
        print(f"   Published: {latest.published_at}")
        print(f"   URL: https://www.youtube.com/watch?v={latest.video_id}")

        # Time since publish
        if latest.published_at:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            time_diff = now - latest.published_at
            hours = time_diff.total_seconds() / 3600
            print(f"   Age: {hours:.1f} hours ago")

            if hours < 0.5:
                print("\n💡 TIP: Video was published very recently (<30 min ago)")
                print("   YouTube's API can take 5-10 minutes to update the uploads playlist.")
                print("   Try waiting a few minutes and fetch again.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_fetch.py <channel_url_or_id>")
        print("Example: python debug_fetch.py https://www.youtube.com/@channelname")
        sys.exit(1)

    channel_input = sys.argv[1]
    asyncio.run(debug_fetch(channel_input))
