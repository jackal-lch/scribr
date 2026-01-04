# Scribr - Detailed Build Plan

**Project Location:** `~/Developer/scribr/`

---

## Quick Reference

| Item | Value |
|------|-------|
| Project Name | Scribr |
| Location | `~/Developer/scribr/` |
| Backend | FastAPI (Python 3.11+) |
| Frontend | React 18 + TypeScript + Vite |
| Database | PostgreSQL |
| Auth | Google OAuth 2.0 |
| Deployment | Railway |
| AI Summaries | Claude API (Anthropic) |
| Notifications | Telegram (user-provided bots) |

---

## Design Decisions (Pre-Approved)

These decisions have already been made - implement as specified:

1. **Authentication**: Google OAuth 2.0
   - Users sign in with their Google account
   - JWT tokens stored in localStorage
   - No email/password option

2. **Database**: PostgreSQL
   - Railway has native PostgreSQL support
   - Use SQLAlchemy 2.0 with async support
   - Alembic for migrations

3. **Framework**: FastAPI + React
   - Backend: FastAPI (async Python)
   - Frontend: React + TypeScript + Vite
   - Styling: TailwindCSS

4. **Telegram Integration**: User-provided bots
   - Each user creates their own Telegram bot via @BotFather
   - User provides bot token and chat ID in settings
   - App sends notifications through user's bot

5. **AI Summaries**: Claude API
   - Use claude-3-haiku for cost efficiency
   - Generate 3-5 bullet point summaries
   - Store summaries in database

6. **MVP Scope**: Full feature set
   - Build all features (spaces, channels, transcripts, scheduling, Telegram)
   - No phased rollout - complete implementation

7. **NotebookLM**: Manual integration only
   - NotebookLM API is enterprise-only
   - Users copy/paste transcripts manually
   - Focus on making copy/download easy

---

## Project Overview

A multi-tenant web application that allows users to:
- Create personal "spaces" to organize content
- Subscribe to multiple YouTube channels per space
- Automatically extract and store video transcripts
- View and copy transcripts for use in NotebookLM or other tools
- Receive Telegram notifications with AI-generated summaries when new videos are uploaded

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Backend | FastAPI (Python 3.11+) | Async, fast, great for APIs |
| Frontend | React 18 + TypeScript + Vite | Modern, type-safe, fast builds |
| Database | PostgreSQL | Robust, Railway-native support |
| ORM | SQLAlchemy 2.0 + Alembic | Async support, migrations |
| Auth | Google OAuth 2.0 | User preference |
| Styling | TailwindCSS | Rapid UI development |
| Background Jobs | APScheduler | In-process, no Redis needed |
| Transcript Extraction | yt-dlp | Best YouTube tool available |
| AI Summaries | Claude API (Anthropic) | High-quality summaries |
| Notifications | Telegram Bot API | User-provided bots |
| Deployment | Railway | User preference |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│                         React + TypeScript                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Login   │  │Dashboard │  │  Space   │  │  Video   │  │ Settings │  │
│  │  Page    │  │  Page    │  │  Detail  │  │  Detail  │  │   Page   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ REST API (JSON)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                     │
│                              FastAPI                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         API Routers                              │   │
│  │  /auth/*    /spaces/*    /channels/*    /videos/*    /users/*   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         Services Layer                           │   │
│  │  YouTubeService  TranscriptService  SummaryService  TelegramSvc │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Background Scheduler                        │   │
│  │              APScheduler (runs daily at configurable time)       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
         │                           │                          │
         ▼                           ▼                          ▼
┌──────────────┐          ┌──────────────────┐         ┌──────────────┐
│  PostgreSQL  │          │  External APIs   │         │   Telegram   │
│              │          │  - YouTube       │         │   Bot API    │
│  - users     │          │  - Claude API    │         │              │
│  - spaces    │          │                  │         │              │
│  - channels  │          └──────────────────┘         └──────────────┘
│  - videos    │
│  - transcripts│
└──────────────┘
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    users    │       │   spaces    │       │  channels   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id (PK)     │──────<│ id (PK)     │──────<│ id (PK)     │
│ email       │       │ user_id(FK) │       │ space_id(FK)│
│ name        │       │ name        │       │ yt_channel_id│
│ google_id   │       │ description │       │ yt_channel_name│
│ tg_bot_token│       │ created_at  │       │ last_checked │
│ tg_chat_id  │       │ updated_at  │       │ created_at  │
│ created_at  │       └─────────────┘       └─────────────┘
└─────────────┘                                    │
                                                   │
                        ┌─────────────┐            │
                        │   videos    │<───────────┘
                        ├─────────────┤
                        │ id (PK)     │
                        │ channel_id(FK)
                        │ yt_video_id │
                        │ title       │
                        │ published_at│
                        │ duration    │
                        │ thumbnail_url│
                        │ created_at  │
                        └─────────────┘
                               │
                               │
                        ┌─────────────┐
                        │ transcripts │
                        ├─────────────┤
                        │ id (PK)     │
                        │ video_id(FK)│
                        │ content     │
                        │ summary     │
                        │ language    │
                        │ word_count  │
                        │ created_at  │
                        └─────────────┘
```

### SQL Schema

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    google_id VARCHAR(255) UNIQUE NOT NULL,
    telegram_bot_token VARCHAR(255),
    telegram_chat_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Spaces table
CREATE TABLE spaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_spaces_user_id ON spaces(user_id);

-- Channels table
CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    youtube_channel_id VARCHAR(255) NOT NULL,
    youtube_channel_name VARCHAR(255),
    youtube_channel_url VARCHAR(500),
    thumbnail_url VARCHAR(500),
    last_checked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(space_id, youtube_channel_id)
);

CREATE INDEX idx_channels_space_id ON channels(space_id);
CREATE INDEX idx_channels_youtube_id ON channels(youtube_channel_id);

-- Videos table
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    youtube_video_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    published_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    thumbnail_url VARCHAR(500),
    view_count INTEGER,
    has_transcript BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_videos_channel_id ON videos(channel_id);
CREATE INDEX idx_videos_youtube_id ON videos(youtube_video_id);
CREATE INDEX idx_videos_published ON videos(published_at DESC);

-- Transcripts table
CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID UNIQUE NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    summary TEXT,
    language VARCHAR(10) DEFAULT 'en',
    word_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_transcripts_video_id ON transcripts(video_id);
```

---

## API Specification

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/google` | Redirect to Google OAuth |
| GET | `/auth/google/callback` | OAuth callback handler |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/logout` | Clear session/token |

### Spaces Endpoints

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/spaces` | List user's spaces | - | `Space[]` |
| POST | `/spaces` | Create new space | `{name, description?}` | `Space` |
| GET | `/spaces/{id}` | Get space details | - | `Space` with stats |
| PUT | `/spaces/{id}` | Update space | `{name?, description?}` | `Space` |
| DELETE | `/spaces/{id}` | Delete space | - | `204` |

### Channels Endpoints

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/spaces/{id}/channels` | List channels in space | - | `Channel[]` |
| POST | `/spaces/{id}/channels` | Add channel | `{url}` | `Channel` |
| DELETE | `/spaces/{id}/channels/{channelId}` | Remove channel | - | `204` |
| POST | `/spaces/{id}/channels/{channelId}/refresh` | Manual refresh | - | `{newVideos: number}` |

### Videos Endpoints

| Method | Endpoint | Description | Query Params | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/spaces/{id}/videos` | List videos in space | `page, limit, channelId?` | `Video[]` with pagination |
| GET | `/videos/{id}` | Get video details | - | `Video` with transcript |
| GET | `/videos/{id}/transcript` | Get transcript content | `format=txt\|md` | Text content |
| GET | `/videos/{id}/transcript/download` | Download as file | `format=txt\|md` | File download |

### User Settings Endpoints

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| GET | `/users/me` | Get user profile | - |
| PUT | `/users/me/telegram` | Update Telegram config | `{botToken, chatId}` |
| POST | `/users/me/telegram/test` | Send test message | - |

---

## Project Structure

```
scribr/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry point
│   │   ├── config.py               # Settings from environment variables
│   │   ├── database.py             # Database connection and session
│   │   │
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── space.py
│   │   │   ├── channel.py
│   │   │   ├── video.py
│   │   │   └── transcript.py
│   │   │
│   │   ├── schemas/                # Pydantic schemas for API
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── space.py
│   │   │   ├── channel.py
│   │   │   ├── video.py
│   │   │   └── transcript.py
│   │   │
│   │   ├── routers/                # API route handlers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py             # Google OAuth endpoints
│   │   │   ├── spaces.py           # Space CRUD
│   │   │   ├── channels.py         # Channel management
│   │   │   ├── videos.py           # Video and transcript endpoints
│   │   │   └── users.py            # User settings
│   │   │
│   │   ├── services/               # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── youtube.py          # yt-dlp wrapper for channel/video info
│   │   │   ├── transcript.py       # Transcript extraction logic
│   │   │   ├── summary.py          # Claude API summarization
│   │   │   └── telegram.py         # Telegram bot notifications
│   │   │
│   │   ├── jobs/                   # Background task definitions
│   │   │   ├── __init__.py
│   │   │   ├── scheduler.py        # APScheduler configuration
│   │   │   └── video_sync.py       # Daily video sync job
│   │   │
│   │   └── utils/                  # Utility functions
│   │       ├── __init__.py
│   │       ├── auth.py             # JWT handling, OAuth helpers
│   │       └── youtube_parser.py   # Parse channel URLs
│   │
│   ├── alembic/                    # Database migrations
│   │   ├── versions/
│   │   ├── env.py
│   │   └── alembic.ini
│   │
│   ├── tests/                      # Backend tests
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_spaces.py
│   │   └── test_youtube.py
│   │
│   ├── requirements.txt            # Python dependencies
│   ├── Dockerfile                  # Backend container
│   └── .env.example                # Example environment variables
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx                # React entry point
│   │   ├── App.tsx                 # Root component with routing
│   │   ├── index.css               # Global styles + Tailwind
│   │   │
│   │   ├── api/                    # API client layer
│   │   │   ├── client.ts           # Axios instance with auth
│   │   │   ├── auth.ts             # Auth API calls
│   │   │   ├── spaces.ts           # Spaces API calls
│   │   │   ├── channels.ts         # Channels API calls
│   │   │   ├── videos.ts           # Videos API calls
│   │   │   └── users.ts            # User settings API calls
│   │   │
│   │   ├── components/             # Reusable UI components
│   │   │   ├── Layout.tsx          # App shell with nav
│   │   │   ├── Header.tsx          # Top navigation bar
│   │   │   ├── Sidebar.tsx         # Side navigation
│   │   │   ├── SpaceCard.tsx       # Space preview card
│   │   │   ├── ChannelCard.tsx     # Channel item display
│   │   │   ├── VideoCard.tsx       # Video thumbnail card
│   │   │   ├── TranscriptViewer.tsx # Transcript display with copy
│   │   │   ├── AddChannelModal.tsx # Modal for adding channels
│   │   │   ├── CreateSpaceModal.tsx # Modal for creating spaces
│   │   │   ├── LoadingSpinner.tsx  # Loading indicator
│   │   │   ├── EmptyState.tsx      # Empty content placeholder
│   │   │   └── Button.tsx          # Styled button component
│   │   │
│   │   ├── pages/                  # Page components
│   │   │   ├── Login.tsx           # Login page
│   │   │   ├── Dashboard.tsx       # Main dashboard (list spaces)
│   │   │   ├── SpaceDetail.tsx     # Single space view
│   │   │   ├── VideoDetail.tsx     # Video + transcript view
│   │   │   └── Settings.tsx        # User settings (Telegram)
│   │   │
│   │   ├── hooks/                  # Custom React hooks
│   │   │   ├── useAuth.ts          # Auth state hook
│   │   │   ├── useSpaces.ts        # Spaces data hook
│   │   │   └── useToast.ts         # Toast notifications
│   │   │
│   │   ├── context/                # React context providers
│   │   │   └── AuthContext.tsx     # Auth state provider
│   │   │
│   │   └── types/                  # TypeScript type definitions
│   │       └── index.ts            # Shared types
│   │
│   ├── public/                     # Static assets
│   │   └── favicon.ico
│   │
│   ├── package.json                # Node dependencies
│   ├── tsconfig.json               # TypeScript config
│   ├── vite.config.ts              # Vite build config
│   ├── tailwind.config.js          # Tailwind config
│   ├── postcss.config.js           # PostCSS config
│   ├── Dockerfile                  # Frontend container
│   └── .env.example                # Example environment variables
│
├── docker-compose.yml              # Local development setup
├── railway.toml                    # Railway deployment config
├── .gitignore
└── README.md
```

---

## Implementation Phases

### Phase 1: Project Initialization (Foundation)

**Backend Setup:**
1. Create `backend/` directory structure
2. Initialize Python virtual environment
3. Create `requirements.txt` with dependencies:
   ```
   fastapi==0.109.0
   uvicorn[standard]==0.27.0
   sqlalchemy[asyncio]==2.0.25
   asyncpg==0.29.0
   alembic==1.13.1
   pydantic==2.5.3
   pydantic-settings==2.1.0
   python-jose[cryptography]==3.3.0
   authlib==1.3.0
   httpx==0.26.0
   yt-dlp==2024.1.1
   anthropic==0.18.1
   python-telegram-bot==21.0
   apscheduler==3.10.4
   python-multipart==0.0.6
   ```
4. Create `app/config.py` - Settings class with env vars
5. Create `app/database.py` - Async SQLAlchemy setup
6. Create `app/main.py` - FastAPI app with CORS

**Database Setup:**
7. Initialize Alembic: `alembic init alembic`
8. Create all SQLAlchemy models in `app/models/`
9. Generate initial migration
10. Create `docker-compose.yml` with PostgreSQL

**Frontend Setup:**
11. Create React app: `npm create vite@latest frontend -- --template react-ts`
12. Install dependencies:
    ```
    npm install axios @tanstack/react-query react-router-dom
    npm install -D tailwindcss postcss autoprefixer
    npm install lucide-react
    ```
13. Configure Tailwind CSS
14. Create `api/client.ts` with Axios instance
15. Set up basic routing in `App.tsx`

**Deliverable:** Project runs locally with database, backend serves health endpoint, frontend shows placeholder page.

---

### Phase 2: Authentication System

**Backend:**
1. Create Google OAuth credentials in Google Cloud Console
2. Implement `app/utils/auth.py`:
   - JWT token creation/validation
   - OAuth state management
3. Implement `app/routers/auth.py`:
   - `GET /auth/google` - Generate OAuth URL, redirect
   - `GET /auth/google/callback` - Handle callback, create/update user, return JWT
   - `GET /auth/me` - Return current user from JWT
   - `POST /auth/logout` - Clear token
4. Create auth dependency for protected routes
5. Add user model and schema

**Frontend:**
6. Create `AuthContext.tsx`:
   - Store JWT in localStorage
   - Provide login/logout functions
   - Auto-refresh on mount
7. Create `Login.tsx` page:
   - "Sign in with Google" button
   - Redirect to backend OAuth endpoint
8. Create `useAuth.ts` hook
9. Add protected route wrapper component
10. Add auth header interceptor to Axios client

**Deliverable:** Users can sign in with Google, JWT is stored, protected routes work.

---

### Phase 3: Spaces Management

**Backend:**
1. Implement `app/schemas/space.py`:
   - `SpaceCreate`, `SpaceUpdate`, `SpaceResponse`
2. Implement `app/routers/spaces.py`:
   - `GET /spaces` - List user's spaces with stats
   - `POST /spaces` - Create new space
   - `GET /spaces/{id}` - Get space with channel/video counts
   - `PUT /spaces/{id}` - Update space name/description
   - `DELETE /spaces/{id}` - Delete space and all contents

**Frontend:**
3. Create `Dashboard.tsx`:
   - Grid of space cards
   - "Create Space" button
   - Empty state when no spaces
4. Create `SpaceCard.tsx`:
   - Space name, description preview
   - Channel count, video count badges
   - Click to navigate to detail
5. Create `CreateSpaceModal.tsx`:
   - Form with name (required) and description (optional)
   - Submit creates space, closes modal, refreshes list
6. Wire up API calls in `api/spaces.ts`
7. Add React Query hooks for data fetching

**Deliverable:** Users can create, view, edit, and delete spaces.

---

### Phase 4: Channel Subscription

**Backend:**
1. Implement `app/utils/youtube_parser.py`:
   - Parse various YouTube channel URL formats:
     - `youtube.com/channel/UC...`
     - `youtube.com/@username`
     - `youtube.com/c/CustomName`
   - Extract channel ID from URL
2. Implement `app/services/youtube.py`:
   - `get_channel_info(channel_id)` - Fetch channel metadata using yt-dlp
   - `get_channel_videos(channel_id, limit)` - List recent videos
3. Implement `app/routers/channels.py`:
   - `GET /spaces/{id}/channels` - List channels in space
   - `POST /spaces/{id}/channels` - Add channel by URL
   - `DELETE /spaces/{id}/channels/{channelId}` - Remove channel
4. Implement `app/schemas/channel.py`

**Frontend:**
5. Update `SpaceDetail.tsx`:
   - List of subscribed channels
   - "Add Channel" button
   - Channel cards with thumbnail, name, video count
6. Create `AddChannelModal.tsx`:
   - Input field for YouTube channel URL
   - Validation feedback
   - Shows channel preview before confirming
7. Create `ChannelCard.tsx`:
   - Thumbnail, name, subscriber count
   - Delete button (with confirmation)

**Deliverable:** Users can subscribe to YouTube channels by URL, view channel list, remove channels.

---

### Phase 5: Video Listing & Transcript Extraction

**Backend:**
1. Extend `app/services/youtube.py`:
   - `get_video_info(video_id)` - Fetch video metadata
   - `list_channel_videos(channel_id, since_date)` - Get videos since date
2. Implement `app/services/transcript.py`:
   - `extract_transcript(video_id)` - Use yt-dlp to get subtitles/captions
   - Support multiple languages (prefer English)
   - Handle videos without transcripts gracefully
   - Format as clean text (remove timestamps)
3. Implement `app/routers/videos.py`:
   - `GET /spaces/{id}/videos` - List all videos in space (paginated)
   - `GET /videos/{id}` - Get video details with transcript
   - `GET /videos/{id}/transcript` - Get transcript as text
   - `GET /videos/{id}/transcript/download` - Download as .txt or .md file
4. Implement initial video fetch when channel is added:
   - On channel subscription, fetch last 50 videos
   - Extract transcripts for all (background task)

**Frontend:**
5. Create `VideoCard.tsx`:
   - Thumbnail, title, channel name, date
   - Duration badge
   - Transcript status indicator (available/processing/unavailable)
6. Update `SpaceDetail.tsx`:
   - Add videos tab/section
   - Filter by channel (dropdown)
   - Infinite scroll or pagination
7. Create `VideoDetail.tsx`:
   - Video metadata (title, channel, date, duration)
   - Embedded YouTube player (optional - iframe)
   - Transcript viewer section
8. Create `TranscriptViewer.tsx`:
   - Display full transcript text
   - "Copy All" button with success feedback
   - "Download as TXT" and "Download as MD" buttons
   - Word count display

**Deliverable:** Users see all videos from subscribed channels, can view and copy transcripts.

---

### Phase 6: Background Jobs & Auto-Sync

**Backend:**
1. Implement `app/jobs/scheduler.py`:
   - Configure APScheduler with async job store
   - Set up daily trigger (configurable time, default 6 AM UTC)
2. Implement `app/jobs/video_sync.py`:
   - `sync_all_channels()` - Main job function:
     - For each channel across all users:
       - Fetch videos since last_checked_at
       - Insert new videos into database
       - Queue transcript extraction for new videos
       - Update channel.last_checked_at
   - `process_transcript_queue()` - Extract transcripts for pending videos
3. Add job startup in `app/main.py` lifespan event
4. Implement manual refresh endpoint:
   - `POST /spaces/{id}/channels/{channelId}/refresh`
   - Triggers immediate sync for single channel
5. Add job status tracking (optional):
   - Last run timestamp
   - Videos processed count
   - Errors encountered

**Frontend:**
6. Add "Refresh" button on channel card
7. Add "Last synced: X hours ago" indicator
8. Add loading state during refresh

**Deliverable:** System automatically checks for new videos daily, manual refresh works.

---

### Phase 7: AI Summaries (Claude)

**Backend:**
1. Implement `app/services/summary.py`:
   - `generate_summary(transcript_text, video_title)`:
     - Use Claude API (claude-3-haiku for cost efficiency)
     - Prompt: Summarize key points in 3-5 bullet points
     - Handle long transcripts (truncate or chunk)
   - Configure max tokens and temperature
2. Integrate summary generation into transcript extraction flow:
   - After transcript is extracted, generate summary
   - Store summary in transcripts table
3. Add summary to API responses
4. Add config for enabling/disabling summaries (per user or global)

**Frontend:**
5. Display summary above full transcript in `VideoDetail.tsx`
6. Show summary in video cards (expandable)
7. Add "Regenerate Summary" button (optional)

**Deliverable:** Each video has an AI-generated summary stored and displayed.

---

### Phase 8: Telegram Notifications

**Backend:**
1. Implement `app/services/telegram.py`:
   - `send_message(bot_token, chat_id, message)`:
     - Use python-telegram-bot or direct API calls
     - Format message with video title, channel, summary, link
   - `validate_bot_token(token)` - Check if token is valid
   - `get_chat_id_instructions()` - Return instructions for user
2. Implement `app/routers/users.py`:
   - `PUT /users/me/telegram` - Save bot token and chat ID
   - `POST /users/me/telegram/test` - Send test message
3. Integrate notifications into video sync job:
   - After processing new video with transcript:
     - If user has Telegram configured:
       - Send notification with summary

**Frontend:**
4. Create `Settings.tsx` page:
   - Input for Telegram bot token
   - Input for chat ID
   - Instructions on how to:
     - Create bot via @BotFather
     - Get chat ID (start conversation with bot, use API)
   - "Test Connection" button
   - Save button

**Message Format:**
```
🎬 New Video: {title}

📺 Channel: {channel_name}

📝 Summary:
{summary_bullet_points}

🔗 Watch: https://youtube.com/watch?v={video_id}
📄 Transcript: {app_url}/videos/{id}
```

**Deliverable:** Users receive Telegram notifications when new videos are processed.

---

### Phase 9: Polish & Error Handling

**Backend:**
1. Add comprehensive error handling:
   - Custom exception classes
   - Global exception handler middleware
   - Proper HTTP status codes
2. Add request validation with detailed error messages
3. Add logging throughout application
4. Add rate limiting for external API calls (YouTube, Claude, Telegram)
5. Add retry logic for transient failures
6. Add health check endpoint: `GET /health`

**Frontend:**
7. Add error boundaries for React
8. Add toast notifications for success/error feedback
9. Add loading skeletons for data fetching
10. Add empty states for all lists
11. Add confirmation dialogs for destructive actions
12. Add responsive design fixes
13. Add keyboard shortcuts (optional):
    - `c` to copy transcript
    - `Escape` to close modals

**Deliverable:** App handles errors gracefully, provides good UX feedback.

---

### Phase 10: Deployment to Railway

**Backend Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for yt-dlp
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile:**
```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Railway Configuration (`railway.toml`):**
```toml
[build]
builder = "dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

**Deployment Steps:**
1. Create Railway project
2. Add PostgreSQL service from Railway dashboard
3. Create backend service:
   - Connect to GitHub repo
   - Set root directory to `backend`
   - Add environment variables
4. Create frontend service:
   - Connect to same repo
   - Set root directory to `frontend`
   - Add `VITE_API_URL` pointing to backend
5. Configure custom domain (optional)
6. Set up monitoring/alerts

**Environment Variables (Railway):**
```
# Backend
DATABASE_URL=<from Railway Postgres>
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
JWT_SECRET=<generate secure random string>
ANTHROPIC_API_KEY=<from Anthropic>
FRONTEND_URL=<your frontend URL>
CORS_ORIGINS=<frontend URL>

# Frontend
VITE_API_URL=<backend URL>
VITE_GOOGLE_CLIENT_ID=<same as backend>
```

**Deliverable:** App is live on Railway, accessible via custom domain.

---

## Environment Variables Reference

### Backend (.env)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/scribr

# Auth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
JWT_SECRET=your-super-secret-jwt-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=168

# External APIs
ANTHROPIC_API_KEY=sk-ant-...

# App Config
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
ENVIRONMENT=development

# Scheduler
SYNC_SCHEDULE_HOUR=6
SYNC_SCHEDULE_MINUTE=0
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

---

## Key Dependencies

### Backend (requirements.txt)

```
# Core
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0

# Database
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0
alembic==1.13.1

# Auth
python-jose[cryptography]==3.3.0
authlib==1.3.0
httpx==0.26.0
python-multipart==0.0.6

# YouTube
yt-dlp==2024.1.1

# AI
anthropic==0.18.1

# Telegram
python-telegram-bot==21.0

# Background Jobs
apscheduler==3.10.4

# Testing
pytest==8.0.0
pytest-asyncio==0.23.3
httpx==0.26.0
```

### Frontend (package.json dependencies)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.3",
    "@tanstack/react-query": "^5.17.19",
    "axios": "^1.6.5",
    "lucide-react": "^0.311.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.33",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.12"
  }
}
```

---

## Testing Strategy

### Backend Tests

1. **Unit Tests:**
   - YouTube URL parser
   - JWT token handling
   - Summary generation (mock Claude API)

2. **Integration Tests:**
   - Auth flow (mock Google OAuth)
   - CRUD operations for spaces, channels, videos
   - Transcript extraction (mock yt-dlp)

3. **E2E Tests (optional):**
   - Full user journey with test database

### Frontend Tests

1. **Component Tests:**
   - SpaceCard, VideoCard, TranscriptViewer
   - Forms and modals

2. **Integration Tests:**
   - Auth flow
   - Navigation
   - API error handling

---

## Security Considerations

1. **Authentication:**
   - JWT tokens with expiration
   - Secure cookie settings in production
   - HTTPS only in production

2. **Authorization:**
   - All endpoints check user ownership
   - Users can only access their own spaces/channels/videos

3. **Input Validation:**
   - Pydantic schemas validate all input
   - SQL injection prevented by ORM

4. **API Keys:**
   - Telegram bot tokens encrypted at rest (optional)
   - Environment variables for all secrets

5. **Rate Limiting:**
   - Limit requests per user
   - Limit external API calls

---

## Monitoring & Maintenance

1. **Logging:**
   - Structured JSON logs
   - Log levels by environment
   - Error tracking

2. **Health Checks:**
   - `/health` endpoint for Railway
   - Database connectivity check

3. **Metrics (optional):**
   - Request latency
   - Job success/failure rates
   - External API call counts

---

## Future Enhancements (Post-MVP)

1. **Search:** Full-text search across transcripts
2. **Export:** Bulk export transcripts as ZIP
3. **Webhooks:** Real-time video notifications via YouTube API
4. **Multiple Languages:** Support transcript translation
5. **Team Spaces:** Share spaces with other users
6. **API Access:** Public API for programmatic access
7. **Mobile App:** React Native companion app
8. **NotebookLM Integration:** If API becomes public

---

## Quick Start Commands

### Initial Setup (Run Once)

```bash
# Create project directory
mkdir -p ~/Developer/scribr
cd ~/Developer/scribr

# Initialize git
git init

# Create backend
mkdir -p backend/app/{models,schemas,routers,services,jobs,utils}
mkdir -p backend/alembic/versions
mkdir -p backend/tests

# Create frontend
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install axios @tanstack/react-query react-router-dom lucide-react
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
cd ..

# Create Python virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

### Development Commands

```bash
# Start PostgreSQL (Docker)
docker-compose up -d db

# Start backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload

# Start frontend (separate terminal)
cd frontend && npm run dev

# Run migrations
cd backend && alembic upgrade head

# Create new migration
cd backend && alembic revision --autogenerate -m "description"
```

---

## Configuration Files (Copy These Exactly)

### docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: scribr-db
    environment:
      POSTGRES_USER: scribr
      POSTGRES_PASSWORD: scribr_dev_password
      POSTGRES_DB: scribr
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### backend/.env.example

```env
# Database
DATABASE_URL=postgresql+asyncpg://scribr:scribr_dev_password@localhost:5432/scribr

# Auth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
JWT_SECRET=change-this-to-a-random-32-char-string
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=168

# External APIs
ANTHROPIC_API_KEY=sk-ant-...

# App Config
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=http://localhost:5173
ENVIRONMENT=development

# Scheduler
SYNC_SCHEDULE_HOUR=6
SYNC_SCHEDULE_MINUTE=0
```

### frontend/.env.example

```env
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

### frontend/tailwind.config.js

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

### frontend/src/index.css

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### .gitignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
venv/
.env
*.egg-info/

# Node
node_modules/
dist/
.env.local

# IDE
.vscode/
.idea/

# OS
.DS_Store

# Docker
postgres_data/
```

---

## Starter Code Templates

### backend/app/config.py

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str

    # Auth
    google_client_id: str
    google_client_secret: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 168

    # External APIs
    anthropic_api_key: str

    # App Config
    frontend_url: str
    cors_origins: str
    environment: str = "development"

    # Scheduler
    sync_schedule_hour: int = 6
    sync_schedule_minute: int = 0

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### backend/app/database.py

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.environment == "development")
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
```

### backend/app/main.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, spaces, channels, videos, users
# from app.jobs.scheduler import start_scheduler, shutdown_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # start_scheduler()
    yield
    # Shutdown
    # shutdown_scheduler()


app = FastAPI(title="Scribr API", version="1.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(spaces.router, prefix="/spaces", tags=["spaces"])
app.include_router(channels.router, tags=["channels"])
app.include_router(videos.router, tags=["videos"])
app.include_router(users.router, prefix="/users", tags=["users"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### backend/app/models/user.py

```python
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    google_id = Column(String(255), unique=True, nullable=False)
    telegram_bot_token = Column(String(255))
    telegram_chat_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    spaces = relationship("Space", back_populates="user", cascade="all, delete-orphan")
```

### backend/app/models/space.py

```python
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Space(Base):
    __tablename__ = "spaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="spaces")
    channels = relationship("Channel", back_populates="space", cascade="all, delete-orphan")
```

### backend/app/models/channel.py

```python
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    youtube_channel_id = Column(String(255), nullable=False, index=True)
    youtube_channel_name = Column(String(255))
    youtube_channel_url = Column(String(500))
    thumbnail_url = Column(String(500))
    last_checked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('space_id', 'youtube_channel_id', name='uq_space_channel'),)

    space = relationship("Space", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")
```

### backend/app/models/video.py

```python
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    youtube_video_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    published_at = Column(DateTime(timezone=True), index=True)
    duration_seconds = Column(Integer)
    thumbnail_url = Column(String(500))
    view_count = Column(Integer)
    has_transcript = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    channel = relationship("Channel", back_populates="videos")
    transcript = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")
```

### backend/app/models/transcript.py

```python
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text)
    language = Column(String(10), default="en")
    word_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="transcript")
```

### backend/app/models/__init__.py

```python
from app.models.user import User
from app.models.space import Space
from app.models.channel import Channel
from app.models.video import Video
from app.models.transcript import Transcript

__all__ = ["User", "Space", "Channel", "Video", "Transcript"]
```

### frontend/src/App.tsx

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import SpaceDetail from './pages/SpaceDetail';
import VideoDetail from './pages/VideoDetail';
import Settings from './pages/Settings';

const queryClient = new QueryClient();

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) return <div>Loading...</div>;
  if (!user) return <Navigate to="/login" />;

  return <>{children}</>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }>
              <Route index element={<Dashboard />} />
              <Route path="spaces/:id" element={<SpaceDetail />} />
              <Route path="videos/:id" element={<VideoDetail />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
```

### frontend/src/api/client.ts

```typescript
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default client;
```

### frontend/src/context/AuthContext.tsx

```tsx
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import client from '../api/client';

interface User {
  id: string;
  email: string;
  name: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      client.get('/auth/me')
        .then((res) => setUser(res.data))
        .catch(() => localStorage.removeItem('token'))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = () => {
    window.location.href = `${import.meta.env.VITE_API_URL}/auth/google`;
  };

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
```

### frontend/src/types/index.ts

```typescript
export interface User {
  id: string;
  email: string;
  name: string;
  telegram_bot_token?: string;
  telegram_chat_id?: string;
}

export interface Space {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  channel_count?: number;
  video_count?: number;
}

export interface Channel {
  id: string;
  space_id: string;
  youtube_channel_id: string;
  youtube_channel_name: string;
  youtube_channel_url: string;
  thumbnail_url?: string;
  last_checked_at?: string;
  video_count?: number;
}

export interface Video {
  id: string;
  channel_id: string;
  youtube_video_id: string;
  title: string;
  description?: string;
  published_at: string;
  duration_seconds?: number;
  thumbnail_url?: string;
  has_transcript: boolean;
  channel_name?: string;
}

export interface Transcript {
  id: string;
  video_id: string;
  content: string;
  summary?: string;
  language: string;
  word_count: number;
}
```

---

## Services Implementation Guide

### backend/app/services/youtube.py

Use yt-dlp to:
1. Parse channel URLs (handle @username, /channel/UC..., /c/name formats)
2. Get channel info (name, thumbnail, subscriber count)
3. List videos from a channel
4. Extract transcripts/subtitles from videos

Key functions needed:
```python
async def get_channel_info(channel_url: str) -> dict
async def get_channel_videos(channel_id: str, limit: int = 50) -> list[dict]
async def get_video_transcript(video_id: str) -> str | None
```

### backend/app/services/summary.py

Use Anthropic Claude API:
```python
from anthropic import Anthropic

async def generate_summary(transcript: str, title: str) -> str:
    client = Anthropic()
    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Summarize this video transcript in 3-5 bullet points:\n\nTitle: {title}\n\nTranscript:\n{transcript[:8000]}"
        }]
    )
    return message.content[0].text
```

### backend/app/services/telegram.py

Use direct API calls or python-telegram-bot:
```python
import httpx

async def send_telegram_message(bot_token: str, chat_id: str, message: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        })
    return response.status_code == 200
```

---

## Implementation Checklist

Use this checklist to track progress:

### Phase 1: Setup
- [ ] Create directory structure
- [ ] Initialize backend (venv, requirements.txt)
- [ ] Initialize frontend (Vite, TailwindCSS)
- [ ] Create docker-compose.yml
- [ ] Create all SQLAlchemy models
- [ ] Set up Alembic and run initial migration
- [ ] Create basic FastAPI app with health endpoint
- [ ] Verify: `docker-compose up -d` and backend/frontend start

### Phase 2: Auth
- [ ] Set up Google OAuth credentials
- [ ] Implement JWT utilities
- [ ] Implement /auth/google endpoint
- [ ] Implement /auth/google/callback endpoint
- [ ] Implement /auth/me endpoint
- [ ] Create AuthContext in React
- [ ] Create Login page
- [ ] Create protected route wrapper
- [ ] Verify: Can sign in with Google and see dashboard

### Phase 3: Spaces
- [ ] Create Space schemas
- [ ] Implement spaces router (CRUD)
- [ ] Create Dashboard page
- [ ] Create SpaceCard component
- [ ] Create CreateSpaceModal
- [ ] Wire up React Query hooks
- [ ] Verify: Can create, view, edit, delete spaces

### Phase 4: Channels
- [ ] Implement YouTube URL parser
- [ ] Implement YouTubeService (channel info)
- [ ] Create Channel schemas
- [ ] Implement channels router
- [ ] Update SpaceDetail page with channels
- [ ] Create AddChannelModal
- [ ] Create ChannelCard component
- [ ] Verify: Can add YouTube channel by URL

### Phase 5: Videos & Transcripts
- [ ] Implement video listing from yt-dlp
- [ ] Implement transcript extraction
- [ ] Create Video/Transcript schemas
- [ ] Implement videos router
- [ ] Create VideoCard component
- [ ] Create VideoDetail page
- [ ] Create TranscriptViewer with copy/download
- [ ] Verify: Can view video list and transcripts

### Phase 6: Background Jobs
- [ ] Set up APScheduler
- [ ] Implement video sync job
- [ ] Add manual refresh endpoint
- [ ] Add refresh button to UI
- [ ] Add "last synced" indicator
- [ ] Verify: Daily sync runs, manual refresh works

### Phase 7: AI Summaries
- [ ] Implement Claude summarization service
- [ ] Integrate into transcript extraction
- [ ] Display summary in VideoDetail
- [ ] Verify: New videos have summaries

### Phase 8: Telegram
- [ ] Implement Telegram service
- [ ] Add telegram settings to users router
- [ ] Create Settings page
- [ ] Add test message functionality
- [ ] Integrate notifications into sync job
- [ ] Verify: Telegram notifications sent for new videos

### Phase 9: Polish
- [ ] Add error handling middleware
- [ ] Add loading skeletons
- [ ] Add toast notifications
- [ ] Add empty states
- [ ] Add confirmation dialogs
- [ ] Test responsive design

### Phase 10: Deploy
- [ ] Create backend Dockerfile
- [ ] Create frontend Dockerfile + nginx.conf
- [ ] Create railway.toml
- [ ] Set up Railway project
- [ ] Configure environment variables
- [ ] Deploy and verify
