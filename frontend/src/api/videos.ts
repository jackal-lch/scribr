import apiClient from './client';

export interface Video {
  id: string;
  youtube_video_id: string;
  title: string;
  published_at: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  // Engagement stats
  view_count: number | null;
  like_count: number | null;
  comment_count: number | null;
  // Metadata
  definition: string | null;  // hd, sd
  caption: boolean | null;  // has YouTube captions
  // Transcript status
  has_transcript: boolean;
  transcript_status: 'pending' | 'extracting' | 'completed' | 'failed';
  transcript_method: 'caption' | 'ai' | 'whisper-mlx' | 'whisper-faster-whisper' | null;  // extraction method
  transcript_error: string | null;  // error message if failed
  channel_name: string | null;
}

export interface VideoDetail extends Video {
  channel_id: string;
  description: string | null;
  tags: string[];
  category_id: string | null;
  default_language: string | null;
  default_audio_language: string | null;
  created_at: string;
}

export interface Transcript {
  id: string;
  video_id: string;
  content: string;
  plain_content: string;
  language: string;
  word_count: number;
  created_at: string;
}

export interface BatchExtractResponse {
  extracted: number;
  extracted_ai: number;
  already_completed: number;
  failed: number;
  total_processed: number;
}

export interface FetchVideosResponse {
  new_videos: number;
  total_videos: number;
}

export interface VideoFilters {
  limit?: number;
  offset?: number;
  sort_by?: 'published_at' | 'view_count' | 'like_count' | 'comment_count' | 'duration_seconds' | 'title';
  sort_order?: 'asc' | 'desc';
  transcript_status?: 'pending' | 'completed' | 'failed' | 'extracting';
  definition?: 'hd' | 'sd';
  has_caption?: boolean;
  search?: string;
}

export async function getChannelVideos(
  channelId: string,
  params?: VideoFilters
): Promise<Video[]> {
  const response = await apiClient.get<Video[]>(`/channels/${channelId}/videos`, { params });
  return response.data;
}

export async function getVideo(videoId: string): Promise<VideoDetail> {
  const response = await apiClient.get<VideoDetail>(`/videos/${videoId}`);
  return response.data;
}

export async function getTranscript(videoId: string): Promise<Transcript> {
  const response = await apiClient.get<Transcript>(`/videos/${videoId}/transcript`);
  return response.data;
}

export async function extractTranscript(
  videoId: string,
  useLocalWhisper: boolean = false
): Promise<VideoDetail> {
  // useLocalWhisper=true: Try CC first, then Local Whisper
  // useLocalWhisper=false: Try CC only (free extraction)
  const params: Record<string, unknown> = { use_ai: useLocalWhisper };
  const response = await apiClient.post<VideoDetail>(
    `/videos/${videoId}/extract-transcript`,
    null,
    { params }
  );
  return response.data;
}

export async function fetchChannelVideos(
  channelId: string,
  limit?: number
): Promise<FetchVideosResponse> {
  const response = await apiClient.post<FetchVideosResponse>(
    `/channels/${channelId}/fetch-videos`,
    limit ? { limit } : {}
  );
  return response.data;
}

export async function extractAllTranscripts(
  channelId: string,
  useLocalWhisper: boolean = false,
  videoIds?: string[]
): Promise<BatchExtractResponse> {
  // useLocalWhisper=true: Try CC first, then Local Whisper for remaining
  // useLocalWhisper=false: Try CC only (free extraction)
  const params: Record<string, unknown> = { use_ai: useLocalWhisper };
  if (videoIds && videoIds.length > 0) {
    params.video_ids = videoIds.join(',');
  }
  const response = await apiClient.post<BatchExtractResponse>(
    `/channels/${channelId}/extract-all-transcripts`,
    null,
    { params }
  );
  return response.data;
}

export interface ExtractionProgress {
  status: 'extracting' | 'complete';
  current?: number;
  total?: number;
  title?: string;
  extracted: number;
  extracted_ai: number;
  failed: number;
  error?: string;
}

export function extractTranscriptsStream(
  channelId: string,
  useLocalWhisper: boolean,
  onProgress: (progress: ExtractionProgress) => void,
  onComplete: (result: ExtractionProgress) => void,
  onError: (error: string) => void,
  videoIds?: string[]
): () => void {
  const baseUrl = apiClient.defaults.baseURL || '';
  const controller = new AbortController();

  // Build URL with query params
  const params = new URLSearchParams();
  params.set('use_ai', String(useLocalWhisper));
  if (videoIds && videoIds.length > 0) {
    params.set('video_ids', videoIds.join(','));
  }

  fetch(`${baseUrl}/channels/${channelId}/extract-transcripts-stream?${params}`, {
    signal: controller.signal,
  })
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to start extraction');
      }
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      const read = (): Promise<void> => {
        return reader.read().then(({ done, value }) => {
          if (done) return;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)) as ExtractionProgress;
                if (data.error) {
                  onError(data.error);
                  return;
                }
                if (data.status === 'complete') {
                  onComplete(data);
                } else {
                  onProgress(data);
                }
              } catch {
                // Ignore parse errors
              }
            }
          }

          return read();
        });
      };

      return read();
    })
    .catch(err => {
      if (err.name !== 'AbortError') {
        onError(err.message || 'Failed to extract transcripts');
      }
    });

  // Return cancel function
  return () => controller.abort();
}

export function formatDuration(seconds: number | null): string {
  if (!seconds) return '--:--';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

export function getYouTubeUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${videoId}`;
}

export async function downloadAudio(
  videoId: string,
  _filename: string,
  onProgress?: (phase: 'preparing' | 'downloading', percent: number) => void
): Promise<string> {
  onProgress?.('preparing', 0);

  const response = await apiClient.get(`/videos/${videoId}/download-audio`, {
    responseType: 'blob',
    onDownloadProgress: (progressEvent) => {
      if (progressEvent.total) {
        const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100);
        onProgress?.('downloading', percent);
      }
    },
  });

  // Create blob URL - caller is responsible for triggering download
  const url = window.URL.createObjectURL(new Blob([response.data]));
  return url;
}

export function triggerDownload(url: string, filename: string): void {
  console.log('triggerDownload called:', { url: url.substring(0, 50), filename });
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  // Delay removal to ensure browser processes the download
  setTimeout(() => link.remove(), 100);
}

export function revokeDownloadUrl(url: string): void {
  window.URL.revokeObjectURL(url);
}

export interface AudioPrepareProgress {
  status: 'downloading' | 'zipping' | 'ready';
  current?: number;
  total?: number;
  title?: string;
  token?: string;
  completed?: number;
  failed?: number;
  error?: string;
}

export function prepareAllAudio(
  channelId: string,
  onProgress: (progress: AudioPrepareProgress) => void,
  onComplete: (token: string) => void,
  onError: (error: string) => void,
  videoIds?: string[]  // Optional: specific video IDs to download
): () => void {
  const baseUrl = apiClient.defaults.baseURL || '';
  const controller = new AbortController();

  // Build URL with optional video_ids query param
  let url = `${baseUrl}/channels/${channelId}/prepare-all-audio`;
  if (videoIds && videoIds.length > 0) {
    url += `?video_ids=${videoIds.join(',')}`;
  }

  fetch(url, {
    signal: controller.signal,
  })
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to start audio preparation');
      }
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      const read = (): Promise<void> => {
        return reader.read().then(({ done, value }) => {
          if (done) return;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)) as AudioPrepareProgress;
                if (data.error) {
                  onError(data.error);
                  return;
                }
                if (data.status === 'ready' && data.token) {
                  onComplete(data.token);
                } else {
                  onProgress(data);
                }
              } catch {
                // Ignore parse errors
              }
            }
          }

          return read();
        });
      };

      return read();
    })
    .catch(err => {
      if (err.name !== 'AbortError') {
        onError(err.message || 'Failed to prepare audio');
      }
    });

  // Return cancel function
  return () => controller.abort();
}

export async function downloadPreparedAudio(token: string): Promise<void> {
  const response = await apiClient.get(`/download-prepared-audio/${token}`, {
    responseType: 'blob',
  });

  // Get filename from Content-Disposition header
  const contentDisposition = response.headers['content-disposition'];
  let filename = 'audio_files.zip';
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^";\n]+)"?/);
    if (match) {
      filename = match[1];
    }
  }

  // Create blob URL and trigger download
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
