import re
from typing import Optional
from urllib.parse import urlparse, parse_qs


def extract_channel_identifier(url: str) -> Optional[dict]:
    """
    Extract channel identifier from various YouTube URL formats.

    Supported formats:
    - https://www.youtube.com/channel/UC... (channel ID)
    - https://www.youtube.com/@username (handle)
    - https://www.youtube.com/c/CustomName (custom URL)
    - https://www.youtube.com/user/username (legacy username)

    Returns:
        dict with 'type' ('channel_id', 'handle', 'custom', 'user') and 'value'
        or None if URL is invalid
    """
    url = url.strip()

    # Add https:// if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urlparse(url)
    except Exception:
        return None

    # Check if it's a YouTube domain
    if not parsed.netloc.replace('www.', '') in ('youtube.com', 'youtu.be'):
        return None

    path = parsed.path.strip('/')

    # Handle @username format
    if path.startswith('@'):
        handle = path.split('/')[0]
        return {'type': 'handle', 'value': handle}

    # Handle /channel/UC... format
    channel_match = re.match(r'^channel/(UC[\w-]+)', path)
    if channel_match:
        return {'type': 'channel_id', 'value': channel_match.group(1)}

    # Handle /c/CustomName format
    custom_match = re.match(r'^c/([\w-]+)', path)
    if custom_match:
        return {'type': 'custom', 'value': custom_match.group(1)}

    # Handle /user/username format (legacy)
    user_match = re.match(r'^user/([\w-]+)', path)
    if user_match:
        return {'type': 'user', 'value': user_match.group(1)}

    # Handle bare username (e.g., youtube.com/mkbhd)
    if path and '/' not in path and not path.startswith(('watch', 'playlist', 'feed', 'shorts')):
        return {'type': 'custom', 'value': path}

    return None


def build_channel_url(identifier: dict) -> str:
    """Build a YouTube channel URL from an identifier."""
    id_type = identifier['type']
    value = identifier['value']

    if id_type == 'channel_id':
        return f'https://www.youtube.com/channel/{value}'
    elif id_type == 'handle':
        return f'https://www.youtube.com/{value}'
    elif id_type == 'custom':
        return f'https://www.youtube.com/c/{value}'
    elif id_type == 'user':
        return f'https://www.youtube.com/user/{value}'

    return f'https://www.youtube.com/{value}'
