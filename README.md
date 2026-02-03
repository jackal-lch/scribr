# Scribr

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)

A self-hosted YouTube transcript manager. Subscribe to channels, extract transcripts, and organize them for AI tools like NotebookLM.

## Features

- **Channel Subscriptions** — Add YouTube channels and automatically fetch their video catalog
- **YouTube Captions** — Extract transcripts from existing captions (free, instant)
- **Local Whisper** — On-device transcription using MLX (Apple Silicon) or faster-whisper (other platforms)
- **Batch Operations** — Extract multiple transcripts or download audio files in bulk
- **Export** — Copy or download transcripts as plain text

## Requirements

- Python 3.11+
- Node.js 18+
- FFmpeg

**macOS:**
```bash
brew install python node ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install python3.11 python3.11-venv nodejs npm ffmpeg
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jackal-lch/scribr.git
cd scribr

# Configure
cp backend/.env.example backend/.env
# Edit backend/.env and add your YOUTUBE_API_KEY

# Run
./start.sh
```

The startup script handles virtual environment setup, dependency installation, and launches both servers.

Open [http://localhost:5173](http://localhost:5173) to get started.

## Configuration

### YouTube Data API (Required)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable **YouTube Data API v3**
3. Create an API key under **Credentials**
4. Add to `backend/.env`:
   ```
   YOUTUBE_API_KEY=your_api_key_here
   ```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `YOUTUBE_API_KEY` | Yes | YouTube Data API v3 key |
| `PROXY_URL` | No | HTTP/SOCKS proxy for yt-dlp |
| `DATABASE_URL` | No | Database URL (default: SQLite) |

## Transcription

Scribr attempts transcription in order:

1. **YouTube Captions** — Extracts existing captions when available
2. **Local Whisper** — Falls back to on-device transcription

### Whisper Backends

| Platform | Backend | Recommended Model |
|----------|---------|-------------------|
| macOS (Apple Silicon) | [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) | turbo |
| Windows / Linux / Intel Mac | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | small |

Download models from the settings dropdown in the navigation bar. Models are cached in `~/.cache/huggingface/hub`.

## Usage

### Adding Channels

Paste any YouTube channel URL:
- `https://www.youtube.com/@channelname`
- `https://www.youtube.com/channel/UC...`

### Extracting Transcripts

| Action | Scope | Method |
|--------|-------|--------|
| **Extract** | Single video | YouTube captions → Whisper |
| **Extract All** | All videos | YouTube captions only |
| **Transcribe All** | All videos | YouTube captions → Whisper |

### Browser Cookies

Some videos require YouTube authentication. Select your browser from the navbar to use its cookies for downloading.

## Project Structure

```
scribr/
├── backend/                 # FastAPI + SQLite
│   ├── app/
│   │   ├── models/          # SQLAlchemy models
│   │   ├── routers/         # API endpoints
│   │   └── services/        # YouTube, Whisper, transcription
│   └── requirements.txt
├── frontend/                # React + TypeScript + Vite
│   └── src/
│       ├── components/
│       ├── pages/
│       └── api/
└── start.sh
```

## Troubleshooting

### Audio download fails

1. Verify FFmpeg is installed: `ffmpeg -version`
2. Select your browser in the navbar (must be logged into YouTube)
3. Try a different browser or configure a proxy via `PROXY_URL`

### No transcript available

The video has no YouTube captions. Download a Whisper model from the navbar settings to enable local transcription.

### Videos require sign-in

Select your browser from the navbar. Scribr uses browser cookies to authenticate with YouTube.

## Contributing

Contributions are welcome. Please open an issue to discuss proposed changes before submitting a pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/description`)
3. Commit your changes
4. Push to the branch (`git push origin feature/description`)
5. Open a pull request

## License

[MIT](LICENSE)
