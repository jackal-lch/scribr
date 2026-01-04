#!/usr/bin/env python3
"""
Rename audio files to add date prefix based on video publish dates.

Usage:
    python rename_audio_with_dates.py /path/to/audio/folder

This script will:
1. Connect to the database
2. Match each audio file to a video by title
3. Rename the file to: YYYYMMDD_original_name.mp3
"""

import os
import re
import sys
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session_maker
from app.models.video import Video


def clean_title(title: str) -> str:
    """Clean title the same way as the download code."""
    return re.sub(r'[<>:"/\\|?*]', '', title).strip()[:80]


def normalize_for_matching(s: str) -> str:
    """Normalize string for fuzzy matching."""
    # Remove extension
    s = re.sub(r'\.(mp3|m4a|wav|webm|ogg)$', '', s, flags=re.IGNORECASE)
    # Lowercase and remove extra whitespace
    s = s.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    return s


async def get_video_dates() -> dict[str, str]:
    """Get mapping of cleaned titles to dates from database."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(Video.title, Video.published_at)
            .where(Video.published_at.isnot(None))
        )

        title_to_date = {}
        for title, published_at in result.all():
            clean = clean_title(title)
            normalized = normalize_for_matching(clean)
            date_str = published_at.strftime("%Y%m%d")
            title_to_date[normalized] = (date_str, clean)

        return title_to_date


def find_matching_date(filename: str, title_to_date: dict) -> tuple[str, str] | None:
    """Find the date for a filename by matching to video titles."""
    normalized = normalize_for_matching(filename)

    # Exact match
    if normalized in title_to_date:
        return title_to_date[normalized]

    # Try partial match (filename might be truncated)
    for title_norm, (date_str, clean_title) in title_to_date.items():
        if title_norm.startswith(normalized) or normalized.startswith(title_norm):
            return (date_str, clean_title)

    return None


async def main():
    if len(sys.argv) < 2:
        print("Usage: python rename_audio_with_dates.py /path/to/audio/folder")
        print("\nThis will rename audio files from:")
        print("  'Video Title.mp3'")
        print("to:")
        print("  '20251230_Video Title.mp3'")
        sys.exit(1)

    folder = Path(sys.argv[1])
    if not folder.exists():
        print(f"Error: Folder not found: {folder}")
        sys.exit(1)

    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    if dry_run:
        print("DRY RUN - no files will be renamed\n")

    print("Loading video dates from database...")
    title_to_date = await get_video_dates()
    print(f"Found {len(title_to_date)} videos with dates\n")

    # Get all audio files
    audio_extensions = {'.mp3', '.m4a', '.wav', '.webm', '.ogg'}
    audio_files = [f for f in folder.iterdir()
                   if f.is_file() and f.suffix.lower() in audio_extensions]

    print(f"Found {len(audio_files)} audio files\n")

    renamed = 0
    skipped = 0
    not_found = 0
    already_has_date = 0

    for audio_file in sorted(audio_files):
        filename = audio_file.name

        # Skip if already has date prefix (YYYYMMDD_)
        if re.match(r'^\d{8}_', filename):
            already_has_date += 1
            continue

        # Find matching date
        match = find_matching_date(filename, title_to_date)

        if match:
            date_str, _ = match
            new_name = f"{date_str}_{filename}"
            new_path = audio_file.parent / new_name

            if new_path.exists():
                print(f"SKIP (exists): {filename}")
                skipped += 1
            else:
                print(f"RENAME: {filename}")
                print(f"    -> {new_name}")
                if not dry_run:
                    audio_file.rename(new_path)
                renamed += 1
        else:
            print(f"NOT FOUND: {filename}")
            not_found += 1

    print(f"\n{'=' * 50}")
    print(f"Summary:")
    print(f"  Renamed: {renamed}")
    print(f"  Already has date: {already_has_date}")
    print(f"  Skipped (exists): {skipped}")
    print(f"  Not found in DB: {not_found}")

    if dry_run and renamed > 0:
        print(f"\nRun without --dry-run to actually rename the files.")


if __name__ == "__main__":
    asyncio.run(main())
