"""
Legacy yt-dlp YouTube service.

NOTE: This module is deprecated. Use youtube_api.py for metadata fetching.
yt-dlp is now only used for transcript extraction (in transcript.py).

This file is kept for reference in case fallback to yt-dlp is needed.
"""

# The following code is preserved for reference but no longer used:
#
# - get_channel_info(): Now in youtube_api.py using YouTube Data API
# - get_channel_videos(): Now in youtube_api.py using YouTube Data API
#
# Transcript extraction remains in transcript.py using yt-dlp
# (YouTube Data API does not provide transcript content)
