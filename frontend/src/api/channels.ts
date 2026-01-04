import apiClient from './client';

export interface Channel {
  id: string;
  user_id: string;
  youtube_channel_id: string;
  youtube_channel_name: string | null;
  youtube_channel_url: string | null;
  thumbnail_url: string | null;
  total_videos: number | null;
  tags: string[];
  last_checked_at: string | null;
  created_at: string;
  video_count: number;
}

export interface ChannelPreview {
  channel_id: string;
  channel_name: string;
  channel_url: string;
  thumbnail_url: string | null;
  total_videos: number | null;
}

export interface AddChannelRequest {
  url: string;
  tags?: string[];
}

export interface UpdateChannelRequest {
  tags: string[];
}

export async function getChannels(tag?: string): Promise<Channel[]> {
  const params = tag ? { tag } : undefined;
  const response = await apiClient.get<Channel[]>('/channels', { params });
  return response.data;
}

export async function getChannel(channelId: string): Promise<Channel> {
  const response = await apiClient.get<Channel>(`/channels/${channelId}`);
  return response.data;
}

export async function previewChannel(url: string): Promise<ChannelPreview> {
  const response = await apiClient.get<ChannelPreview>('/channels/preview', {
    params: { url },
  });
  return response.data;
}

export async function addChannel(data: AddChannelRequest): Promise<Channel> {
  const response = await apiClient.post<Channel>('/channels', data);
  return response.data;
}

export async function updateChannel(channelId: string, data: UpdateChannelRequest): Promise<Channel> {
  const response = await apiClient.put<Channel>(`/channels/${channelId}`, data);
  return response.data;
}

export async function deleteChannel(channelId: string): Promise<void> {
  await apiClient.delete(`/channels/${channelId}`);
}

export async function getAllTags(): Promise<string[]> {
  const response = await apiClient.get<string[]>('/channels/tags/all');
  return response.data;
}
