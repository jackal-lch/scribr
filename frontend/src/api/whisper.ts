import apiClient from './client';

export interface WhisperModel {
  name: string;
  size_mb: number;
  installed: boolean;
  backend?: string;
}

export interface BackendInfo {
  backend: string;
  platform: string;
  arch: string;
  is_apple_silicon: boolean;
  mlx_available: boolean;
}

export interface WhisperSettings {
  selected_model: string;
  models: WhisperModel[];
  backend: string;
  backend_info?: BackendInfo;
}

export interface DownloadProgress {
  status: 'downloading' | 'completed' | 'error';
  percent: number;
  model: string;
  error?: string;
}

export async function getWhisperSettings(): Promise<WhisperSettings> {
  const response = await apiClient.get<WhisperSettings>('/whisper/models');
  return response.data;
}

export async function selectWhisperModel(model: string): Promise<void> {
  await apiClient.put('/whisper/model', { model });
}

export function downloadWhisperModel(
  model: string,
  onProgress: (progress: DownloadProgress) => void,
  onComplete: () => void,
  onError: (error: string) => void
): () => void {
  const baseUrl = apiClient.defaults.baseURL || '';
  const controller = new AbortController();

  fetch(`${baseUrl}/whisper/download/${model}`, {
    method: 'POST',
    signal: controller.signal,
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error('Failed to start model download');
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
                const data = JSON.parse(line.slice(6)) as DownloadProgress;
                if (data.status === 'error') {
                  onError(data.error || 'Download failed');
                  return;
                }
                if (data.status === 'completed') {
                  onProgress(data);
                  onComplete();
                  return;
                }
                onProgress(data);
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
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err.message || 'Failed to download model');
      }
    });

  // Return cancel function
  return () => controller.abort();
}

export function formatModelSize(sizeMb: number): string {
  if (sizeMb >= 1000) {
    return `${(sizeMb / 1000).toFixed(1)} GB`;
  }
  return `${sizeMb} MB`;
}
