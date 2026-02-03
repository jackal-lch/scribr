<p align="center">
  <img src="frontend/public/logo.png" alt="Scribr" width="120" />
</p>

<p align="center">
  A personal YouTube transcript manager. Subscribe to channels, extract transcripts, and organize them for AI tools like NotebookLM.
</p>

<p align="center">
  <em>Note: This project was vibe coded with basic security checks only. Intended for local use. Use at your own risk.</em>
</p>

## Features

- **Channel Management** - Add YouTube channels and fetch their video catalog
- **YouTube Captions** - Extract transcripts from existing captions (free, instant)
- **Local Whisper** - On-device transcription using MLX (Apple Silicon) or faster-whisper (Windows/Linux/Intel Mac)
- **Batch Operations** - Extract multiple transcripts or download audio files in bulk
- **Export** - Copy or download transcripts as text files

## Requirements

- Python 3.11+
- Node.js 18+
- FFmpeg

### Install (macOS)

```bash
brew install python node ffmpeg
```

### Install (Ubuntu/Debian)

```bash
sudo apt install python3.11 python3.11-venv nodejs npm ffmpeg
```

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/user/scribr.git
cd scribr
cp backend/.env.example backend/.env
```

Edit `backend/.env` and add your `YOUTUBE_API_KEY` (see [Getting API Keys](#getting-api-keys)).

### 2. Run

```bash
./start.sh
```

This script:
- Checks for required dependencies
- Creates Python virtual environment
- Installs backend and frontend dependencies
- Installs MLX Whisper on Apple Silicon
- Starts both servers

### 3. Open

Visit [http://localhost:5173](http://localhost:5173)

## Getting API Keys

### YouTube Data API (Required)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable "YouTube Data API v3"
3. Create an API key under Credentials
4. Add to `backend/.env` as `YOUTUBE_API_KEY`

## Transcription Methods

Scribr tries transcription in this order:

1. **YouTube Captions** - Extracts existing captions (free, instant)
2. **Local Whisper** - Uses on-device model if installed

### Local Whisper Backends

| Platform | Backend | Models |
|----------|---------|--------|
| macOS (Apple Silicon) | MLX Whisper | turbo, large-v3-turbo, medium |
| Windows/Linux/Intel Mac | faster-whisper | tiny, base, small, medium, large-v3 |

Download models from the navbar dropdown. Models are cached in `~/.cache/huggingface/hub`.

## Usage

### Adding Channels

Paste any YouTube channel URL:
- `https://www.youtube.com/@channelname`
- `https://www.youtube.com/channel/UC...`

### Extracting Transcripts

- **Single video**: Click "Extract" on any video
- **Batch (captions only)**: Click "Extract All" - uses YouTube captions only
- **Batch (with Whisper)**: Click "Transcribe All" - uses captions, then local Whisper

### Navbar Settings

- **Whisper Model**: Select and download local transcription models
- **Browser Cookies**: Choose browser for YouTube authentication (needed for some videos)

## Architecture

```
scribr/
├── backend/              # FastAPI + SQLite
│   ├── app/
│   │   ├── main.py
│   │   ├── models/       # SQLAlchemy models
│   │   ├── routers/      # API endpoints
│   │   └── services/     # YouTube, Whisper, transcription
│   └── requirements.txt
├── frontend/             # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── api/
│   └── package.json
└── start.sh              # Startup script
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `YOUTUBE_API_KEY` | Yes | YouTube Data API v3 key |
| `FRONTEND_URL` | No | Frontend URL (default: http://localhost:5173) |
| `CORS_ORIGINS` | No | Allowed CORS origins (default: http://localhost:5173) |
| `PROXY_URL` | No | HTTP/SOCKS proxy for yt-dlp |
| `DATABASE_URL` | No | Database URL (default: SQLite) |

## Troubleshooting

### "Failed to download audio"

1. Ensure FFmpeg is installed: `ffmpeg -version`
2. Select your browser in navbar (must be logged into YouTube)
3. Try a different browser

### "No transcript available"

- Video has no YouTube captions
- Download a Whisper model from the navbar dropdown

### Videos require sign-in

Select your browser from the navbar. Scribr uses browser cookies to access YouTube.

## License

MIT License - see [LICENSE](LICENSE)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test
4. Submit a pull request
