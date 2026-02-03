import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { extractTranscript, formatDuration, getYouTubeUrl, downloadAudio, triggerDownload, revokeDownloadUrl } from '../api/videos';
import type { Video } from '../api/videos';

interface VideoCardProps {
  video: Video;
  channelId: string;
  onViewTranscript: (videoId: string) => void;
  isSelected?: boolean;
  onSelectChange?: (videoId: string, selected: boolean) => void;
  showCheckbox?: boolean;
}

export default function VideoCard({ video, channelId, onViewTranscript, isSelected, onSelectChange, showCheckbox }: VideoCardProps) {
  const queryClient = useQueryClient();

  const extractFreeMutation = useMutation({
    mutationFn: () => extractTranscript(video.id, false),

    onMutate: async () => {
      // Cancel queries with partial key match
      await queryClient.cancelQueries({ queryKey: ['channelVideos', channelId] });

      // Snapshot all matching queries for rollback
      const previousData = queryClient.getQueriesData<Video[]>({
        queryKey: ['channelVideos', channelId]
      });

      // Update all matching queries optimistically
      queryClient.setQueriesData<Video[]>(
        { queryKey: ['channelVideos', channelId] },
        (old) => old?.map((v) => v.id === video.id
          ? { ...v, transcript_status: 'extracting' as const }
          : v
        )
      );

      return { previousData };
    },

    onError: (_err, _vars, context) => {
      // Rollback all queries to previous state
      context?.previousData?.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data);
      });
      toast.error('No captions available - try Whisper');
    },

    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['channelVideos', channelId] });
      if (data.has_transcript) {
        toast.success('Transcript extracted from captions');
      } else {
        toast.error('No captions available - try Whisper');
      }
    },
  });

  const extractWhisperMutation = useMutation({
    mutationFn: () => extractTranscript(video.id, true),

    onMutate: async () => {
      // Cancel queries with partial key match
      await queryClient.cancelQueries({ queryKey: ['channelVideos', channelId] });

      // Snapshot all matching queries for rollback
      const previousData = queryClient.getQueriesData<Video[]>({
        queryKey: ['channelVideos', channelId]
      });

      // Update all matching queries optimistically
      queryClient.setQueriesData<Video[]>(
        { queryKey: ['channelVideos', channelId] },
        (old) => old?.map((v) => v.id === video.id
          ? { ...v, transcript_status: 'extracting' as const }
          : v
        )
      );

      return { previousData };
    },

    onError: (_err, _vars, context) => {
      // Rollback all queries to previous state
      context?.previousData?.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data);
      });
      toast.error('Failed to extract transcript');
    },

    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['channelVideos', channelId] });
      if (data.has_transcript) {
        toast.success('Transcript extracted');
      } else {
        toast.error('Failed to extract transcript');
      }
    },
  });

  const [downloadState, setDownloadState] = useState<{
    active: boolean;
    phase: 'preparing' | 'downloading';
    percent: number;
  }>({ active: false, phase: 'preparing', percent: 0 });

  const isExtracting = extractFreeMutation.isPending || extractWhisperMutation.isPending;
  const isDownloading = downloadState.active;

  const handleDownloadAudio = async () => {
    setDownloadState({ active: true, phase: 'preparing', percent: 0 });
    try {
      // Format: YYYYMMDD_title.mp3
      const datePrefix = video.published_at
        ? new Date(video.published_at).toISOString().slice(0, 10).replace(/-/g, '') + '_'
        : '';
      const safeTitle = video.title.slice(0, 80).replace(/[<>:"/\\|?*]/g, '').trim();
      const filename = `${datePrefix}${safeTitle}.mp3`;
      const blobUrl = await downloadAudio(video.id, filename, (phase, percent) => {
        setDownloadState({ active: true, phase, percent });
      });
      // Trigger download immediately since this is from a user click
      triggerDownload(blobUrl, filename);
      revokeDownloadUrl(blobUrl);
      toast.success('Audio downloaded');
    } catch {
      toast.error('Failed to download audio');
    } finally {
      setDownloadState({ active: false, phase: 'preparing', percent: 0 });
    }
  };

  const renderDownloadButton = () => {
    if (downloadState.active) {
      const showIndeterminate = downloadState.phase === 'preparing' || downloadState.percent === 0;
      return (
        <span className="flex items-center gap-2">
          <span className="relative w-16 h-1.5 bg-gray-300 rounded-full overflow-hidden">
            {showIndeterminate ? (
              <span
                className="absolute h-full w-4 bg-blue-500 rounded-full"
                style={{ animation: 'progress-slide 1s ease-in-out infinite' }}
              />
            ) : (
              <span
                className="absolute h-full bg-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${downloadState.percent}%`, left: 0 }}
              />
            )}
          </span>
          {showIndeterminate ? 'Fetching...' : `${downloadState.percent}%`}
        </span>
      );
    }
    return 'Download Audio';
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Unknown date';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatNumber = (n: number | null) => {
    if (n === null || n === undefined) return null;
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
    return n.toString();
  };

  const getStatusBadge = () => {
    switch (video.transcript_status) {
      case 'completed':
        // Show method badge for completed transcripts
        const isAi = video.transcript_method === 'ai' || video.transcript_method?.startsWith('whisper-');
        return (
          <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
            isAi ? 'bg-purple-100 text-purple-800' : 'bg-green-100 text-green-800'
          }`}>
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            {isAi ? 'AI' : 'CC'}
          </span>
        );
      case 'extracting':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Extracting...
          </span>
        );
      case 'failed':
        return (
          <span
            className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 cursor-help"
            title={video.transcript_error || 'Extraction failed'}
          >
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
            Failed
          </span>
        );
      default:
        // Pending - don't show CC/AI prediction since YouTube API doesn't report auto-generated captions
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
            Pending
          </span>
        );
    }
  };

  return (
    <div className={`bg-white rounded-xl shadow-sm border overflow-hidden hover:shadow-md transition-shadow ${
      isSelected ? 'border-blue-500 ring-1 ring-blue-500' : 'border-gray-200'
    }`}>
      <div className="flex">
        {/* Checkbox */}
        {showCheckbox && (
          <div className="flex items-center justify-center w-12 flex-shrink-0 bg-gray-50 border-r border-gray-200">
            <input
              type="checkbox"
              checked={isSelected || false}
              onChange={(e) => onSelectChange?.(video.id, e.target.checked)}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 cursor-pointer"
            />
          </div>
        )}
        {/* Thumbnail */}
        <div className="relative flex-shrink-0 w-40 flex items-center bg-black">
          <a
            href={getYouTubeUrl(video.youtube_video_id)}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full aspect-video"
          >
            {video.thumbnail_url ? (
              <img
                src={video.thumbnail_url}
                alt={video.title}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full bg-gray-200 flex items-center justify-center">
                <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            )}
            {/* Duration badge */}
            <span className="absolute bottom-1 right-1 bg-black/80 text-white text-xs px-1.5 py-0.5 rounded">
              {formatDuration(video.duration_seconds)}
            </span>
          </a>
        </div>

        {/* Content */}
        <div className="flex-1 p-4 min-w-0">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <a
                href={getYouTubeUrl(video.youtube_video_id)}
                target="_blank"
                rel="noopener noreferrer"
                className="block"
              >
                <h3 className="font-medium text-gray-900 line-clamp-2 hover:text-blue-600">
                  {video.title}
                </h3>
              </a>
              <div className="mt-1 flex items-center gap-2 text-sm text-gray-500 flex-wrap">
                <span>{formatDate(video.published_at)}</span>
                {formatNumber(video.view_count) && (
                  <>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      {formatNumber(video.view_count)}
                    </span>
                  </>
                )}
                {formatNumber(video.like_count) && (
                  <>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                      </svg>
                      {formatNumber(video.like_count)}
                    </span>
                  </>
                )}
                {formatNumber(video.comment_count) && (
                  <>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>
                      {formatNumber(video.comment_count)}
                    </span>
                  </>
                )}
                {video.definition === 'hd' && (
                  <>
                    <span>•</span>
                    <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-medium">HD</span>
                  </>
                )}
                {video.caption && (
                  <>
                    <span>•</span>
                    <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-medium">CC</span>
                  </>
                )}
              </div>
            </div>
            <div className="flex-shrink-0">
              {getStatusBadge()}
            </div>
          </div>

          {/* Actions */}
          <div className="mt-3">
            {video.transcript_status === 'completed' ? (
              <button
                onClick={() => onViewTranscript(video.id)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors cursor-pointer"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                View Transcript
              </button>
            ) : video.transcript_status === 'extracting' ? (
              <span className="text-sm text-gray-500">Extracting transcript...</span>
            ) : video.transcript_status === 'failed' ? (
              <div className="flex flex-col gap-2">
                {video.transcript_error && (
                  <p className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
                    {video.transcript_error}
                  </p>
                )}
                <div className="flex items-center gap-1">
                  <span className="text-xs text-gray-500 mr-1">Retry:</span>
                  <button
                    onClick={() => extractFreeMutation.mutate()}
                    disabled={isExtracting || isDownloading}
                    className="inline-flex items-center gap-1 p-1 text-xs font-medium text-green-700 hover:bg-green-50 rounded transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                    title="Extract from captions"
                  >
                    <span className="w-6 h-6 flex items-center justify-center bg-green-100 text-green-700 text-[10px] font-bold rounded">CC</span>
                    {extractFreeMutation.isPending && <span>...</span>}
                  </button>
                  <button
                    onClick={() => extractWhisperMutation.mutate()}
                    disabled={isExtracting || isDownloading}
                    className="inline-flex items-center gap-1 p-1 text-xs font-medium text-blue-700 hover:bg-blue-50 rounded transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                    title="Transcribe with Whisper"
                  >
                    <span className="w-6 h-6 flex items-center justify-center bg-blue-100 text-blue-700 text-[10px] font-bold rounded">AI</span>
                    {extractWhisperMutation.isPending && <span>...</span>}
                  </button>
                  <button
                    onClick={handleDownloadAudio}
                    disabled={isExtracting || isDownloading}
                    className="inline-flex items-center gap-1 p-1 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                    title="Download audio"
                  >
                    {isDownloading ? (
                      renderDownloadButton()
                    ) : (
                      <span className="w-6 h-6 flex items-center justify-center bg-gray-100 text-gray-600 rounded">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                      </span>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-1">
                <span className="text-xs text-gray-500 mr-1">Extract:</span>
                <button
                  onClick={() => extractFreeMutation.mutate()}
                  disabled={isExtracting || isDownloading}
                  className="inline-flex items-center gap-1 p-1 text-xs font-medium text-green-700 hover:bg-green-50 rounded transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                  title="Extract from captions"
                >
                  <span className="w-6 h-6 flex items-center justify-center bg-green-100 text-green-700 text-[10px] font-bold rounded">CC</span>
                  {extractFreeMutation.isPending && <span>...</span>}
                </button>
                <button
                  onClick={() => extractWhisperMutation.mutate()}
                  disabled={isExtracting || isDownloading}
                  className="inline-flex items-center gap-1 p-1 text-xs font-medium text-blue-700 hover:bg-blue-50 rounded transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                  title="Transcribe with Whisper"
                >
                  <span className="w-6 h-6 flex items-center justify-center bg-blue-100 text-blue-700 text-[10px] font-bold rounded">AI</span>
                  {extractWhisperMutation.isPending && <span>...</span>}
                </button>
                <button
                  onClick={handleDownloadAudio}
                  disabled={isExtracting || isDownloading}
                  className="inline-flex items-center gap-1 p-1 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                  title="Download audio"
                >
                  {isDownloading ? (
                    renderDownloadButton()
                  ) : (
                    <span className="w-6 h-6 flex items-center justify-center bg-gray-100 text-gray-600 rounded">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                    </span>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
