export interface User {
  id: string;
  email: string;
  name: string;
  telegram_bot_token?: string;
  telegram_chat_id?: string;
}

export interface Channel {
  id: string;
  user_id: string;
  youtube_channel_id: string;
  youtube_channel_name: string;
  youtube_channel_url: string;
  thumbnail_url?: string;
  total_videos?: number;
  tags: string[];
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
