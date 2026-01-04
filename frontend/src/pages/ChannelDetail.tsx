import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getChannel, deleteChannel } from '../api/channels';
import { getChannelVideos, fetchChannelVideos, extractAllTranscripts, prepareAllAudio, downloadPreparedAudio, AI_PROVIDERS } from '../api/videos';
import type { VideoFilters, AiProvider, AudioPrepareProgress } from '../api/videos';
import VideoCard from '../components/VideoCard';
import TranscriptModal from '../components/TranscriptModal';

type SortBy = 'published_at' | 'view_count' | 'like_count' | 'duration_seconds' | 'title';
type Tab = 'pending' | 'extracted';

export default function ChannelDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [transcriptVideoId, setTranscriptVideoId] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Tab and sorting state
  const [activeTab, setActiveTab] = useState<Tab>('pending');
  const [sortBy, setSortBy] = useState<SortBy>('published_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Filter state
  const [filterDefinition, setFilterDefinition] = useState<'all' | 'hd' | 'sd'>('all');
  const [filterCaption, setFilterCaption] = useState<'all' | 'cc' | 'no-cc'>('all');

  // Selection state
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<string>>(new Set());

  // Debounce search
  useMemo(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Build query params (fetch all, filter client-side by tab)
  const queryParams: VideoFilters = useMemo(() => {
    const params: VideoFilters = {
      sort_by: sortBy,
      sort_order: sortOrder,
    };
    if (debouncedSearch) {
      params.search = debouncedSearch;
    }
    if (filterDefinition !== 'all') {
      params.definition = filterDefinition;
    }
    if (filterCaption !== 'all') {
      params.has_caption = filterCaption === 'cc';
    }
    return params;
  }, [sortBy, sortOrder, debouncedSearch, filterDefinition, filterCaption]);

  const { data: channel, isLoading: channelLoading, error: channelError } = useQuery({
    queryKey: ['channel', id],
    queryFn: () => getChannel(id!),
    enabled: !!id,
  });

  const { data: allVideos = [], isLoading: videosLoading } = useQuery({
    queryKey: ['channelVideos', id, queryParams],
    queryFn: () => getChannelVideos(id!, queryParams),
    enabled: !!id,
  });

  // Group videos by tab
  const videosByTab = useMemo(() => {
    const pending = allVideos.filter(v => v.transcript_status !== 'completed');
    const extracted = allVideos.filter(v => v.transcript_status === 'completed');
    return { pending, extracted };
  }, [allVideos]);

  // Count pending videos
  const pendingStats = useMemo(() => {
    return { total: videosByTab.pending.length };
  }, [videosByTab.pending]);

  // Get videos for current tab
  const videos = videosByTab[activeTab];

  // Selection handlers
  const handleSelectVideo = useCallback((videoId: string, selected: boolean) => {
    setSelectedVideoIds(prev => {
      const next = new Set(prev);
      if (selected) {
        next.add(videoId);
      } else {
        next.delete(videoId);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    const pendingIds = videosByTab.pending.map(v => v.id);
    setSelectedVideoIds(new Set(pendingIds));
  }, [videosByTab.pending]);

  const handleDeselectAll = useCallback(() => {
    setSelectedVideoIds(new Set());
  }, []);

  // Count of selected pending videos (only pending videos can be downloaded)
  const selectedPendingCount = useMemo(() => {
    const pendingIds = new Set(videosByTab.pending.map(v => v.id));
    return Array.from(selectedVideoIds).filter(id => pendingIds.has(id)).length;
  }, [selectedVideoIds, videosByTab.pending]);

  const fetchMutation = useMutation({
    mutationFn: () => fetchChannelVideos(id!),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['channel', id] });
      queryClient.invalidateQueries({ queryKey: ['channelVideos', id] });
      queryClient.invalidateQueries({ queryKey: ['channels'] });
      if (data.new_videos > 0) {
        toast.success(`Found ${data.new_videos} new videos`);
      } else {
        toast.info('No new videos found');
      }
    },
    onError: () => {
      toast.error('Failed to fetch videos');
    },
  });

  const extractFreeMutation = useMutation({
    mutationFn: () => extractAllTranscripts(id!, false),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['channelVideos', id] });
      if (data.extracted > 0) {
        toast.success(`Extracted ${data.extracted} transcripts from captions`);
      } else {
        toast.info('No new transcripts extracted');
      }
      if (data.failed > 0) {
        toast.warning(`${data.failed} failed to extract`);
      }
    },
    onError: () => {
      toast.error('Failed to extract transcripts');
    },
  });

  const [extractingProvider, setExtractingProvider] = useState<AiProvider | null>(null);

  // ZIP download state with progress
  const [audioProgress, setAudioProgress] = useState<AudioPrepareProgress | null>(null);
  const cancelPrepareRef = useRef<(() => void) | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (cancelPrepareRef.current) {
        cancelPrepareRef.current();
      }
    };
  }, []);

  const handleDownloadZip = useCallback((useSelection: boolean) => {
    if (!id) return;

    // Determine which videos to download
    let videoIdsToDownload: string[] | undefined;
    let count: number;

    if (useSelection && selectedPendingCount > 0) {
      // Download only selected pending videos
      const pendingIds = new Set(videosByTab.pending.map(v => v.id));
      videoIdsToDownload = Array.from(selectedVideoIds).filter(id => pendingIds.has(id));
      count = videoIdsToDownload.length;
    } else {
      // Download all pending videos
      count = videosByTab.pending.length;
    }

    if (count === 0) {
      toast.info('No videos to download');
      return;
    }

    toast.info(`Preparing ${count} audio file${count > 1 ? 's' : ''} as ZIP...`);

    // Start SSE connection for progress
    const cancel = prepareAllAudio(
      id,
      (progress) => {
        setAudioProgress(progress);
      },
      async (token) => {
        // Download complete, get the ZIP
        setAudioProgress({ status: 'ready', completed: audioProgress?.completed });
        try {
          await downloadPreparedAudio(token);
          toast.success('ZIP download started');
          // Clear selection after successful download
          if (useSelection) {
            setSelectedVideoIds(new Set());
          }
        } catch {
          toast.error('Failed to download ZIP');
        }
        setAudioProgress(null);
        cancelPrepareRef.current = null;
      },
      (error) => {
        toast.error(error);
        setAudioProgress(null);
        cancelPrepareRef.current = null;
      },
      videoIdsToDownload
    );

    cancelPrepareRef.current = cancel;
  }, [id, videosByTab.pending, selectedVideoIds, selectedPendingCount, audioProgress?.completed]);

  const handleCancelDownload = useCallback(() => {
    if (cancelPrepareRef.current) {
      cancelPrepareRef.current();
      cancelPrepareRef.current = null;
      setAudioProgress(null);
      toast.info('Download cancelled');
    }
  }, []);

  const extractAiMutation = useMutation({
    mutationFn: (provider: AiProvider) => extractAllTranscripts(id!, true, provider),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['channelVideos', id] });
      setExtractingProvider(null);
      const total = data.extracted + data.extracted_ai;
      if (total > 0) {
        toast.success(`Extracted ${total} transcripts (${data.extracted} from captions, ${data.extracted_ai} from AI)`);
      } else {
        toast.info('No new transcripts extracted');
      }
      if (data.failed > 0) {
        toast.warning(`${data.failed} failed to extract`);
      }
    },
    onError: () => {
      setExtractingProvider(null);
      toast.error('Failed to extract transcripts');
    },
  });

  const handleBulkAiExtract = (provider: AiProvider) => {
    const providerName = AI_PROVIDERS.find(p => p.id === provider)?.name || provider;
    if (confirm(`This will try free extraction first, then use ${providerName} for videos without subtitles. Continue?`)) {
      setExtractingProvider(provider);
      extractAiMutation.mutate(provider);
    }
  };

  const deleteMutation = useMutation({
    mutationFn: () => deleteChannel(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] });
      toast.success('Channel deleted');
      navigate('/');
    },
    onError: () => {
      toast.error('Failed to delete channel');
    },
  });

  if (channelLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-8"></div>
          <div className="space-y-4">
            <div className="h-24 bg-gray-200 rounded-xl"></div>
            <div className="h-24 bg-gray-200 rounded-xl"></div>
          </div>
        </div>
      </div>
    );
  }

  if (channelError || !channel) {
    return (
      <div className="p-6">
        <div className="text-center py-12">
          <div className="text-gray-400 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">Channel not found</h3>
          <p className="text-gray-500 mb-4">The channel you're looking for doesn't exist.</p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link to="/" className="hover:text-gray-700">Dashboard</Link>
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span className="text-gray-900">{channel.youtube_channel_name}</span>
      </nav>

      {/* Channel Header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-start gap-4">
          {channel.thumbnail_url ? (
            <img
              src={channel.thumbnail_url}
              alt={channel.youtube_channel_name || 'Channel'}
              className="w-20 h-20 rounded-full object-cover flex-shrink-0"
            />
          ) : (
            <div className="w-20 h-20 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
              <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
          )}

          <div className="flex-1">
            <h1 className="text-2xl font-bold text-gray-900 mb-1">
              {channel.youtube_channel_name || 'Unknown Channel'}
            </h1>
            {channel.youtube_channel_url && (
              <a
                href={channel.youtube_channel_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800"
              >
                View on YouTube
              </a>
            )}
            <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
              <span>{channel.video_count}{channel.total_videos ? ` of ${channel.total_videos}` : ''} videos</span>
              <span className="text-green-600">{videosByTab.extracted.length} transcripts</span>
              {channel.tags.length > 0 && (
                <div className="flex gap-1">
                  {channel.tags.map((tag) => (
                    <span key={tag} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchMutation.mutate()}
              disabled={fetchMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors font-medium disabled:opacity-50"
            >
              {fetchMutation.isPending ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Fetching...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Fetch Videos
                </>
              )}
            </button>

            {!showDeleteConfirm ? (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                title="Delete channel"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                  className="px-3 py-1 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Confirm'}
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-8">
          <button
            onClick={() => setActiveTab('pending')}
            className={`pb-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'pending'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Pending
            <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
              activeTab === 'pending' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'
            }`}>
              {videosByTab.pending.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('extracted')}
            className={`pb-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'extracted'
                ? 'border-green-600 text-green-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Extracted
            <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
              activeTab === 'extracted' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600'
            }`}>
              {videosByTab.extracted.length}
            </span>
          </button>
        </nav>
      </div>

      {/* Extract Actions (only show in Pending tab) */}
      {activeTab === 'pending' && videosByTab.pending.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm divide-y divide-gray-100 mb-6">
          {/* Free CC extraction row */}
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center justify-center w-8 h-8 bg-green-600 text-white text-xs font-bold rounded-lg">CC</span>
              <div>
                <div className="text-sm font-medium text-gray-900">{pendingStats.total} pending videos</div>
                <div className="text-xs text-gray-500">Try free extraction from YouTube subtitles first</div>
              </div>
            </div>
            <button
              onClick={() => extractFreeMutation.mutate()}
              disabled={extractFreeMutation.isPending || extractAiMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium disabled:opacity-50 text-sm"
            >
              {extractFreeMutation.isPending ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Extracting...
                </>
              ) : (
                'Extract Free'
              )}
            </button>
          </div>

          {/* AI extraction row */}
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center justify-center w-8 h-8 bg-purple-600 text-white text-xs font-bold rounded-lg">AI</span>
              <div>
                <div className="text-sm font-medium text-gray-900">Use AI for remaining</div>
                <div className="text-xs text-gray-500">Tries free first, then AI transcription for videos without subtitles</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {AI_PROVIDERS.map((provider) => (
                <button
                  key={provider.id}
                  onClick={() => handleBulkAiExtract(provider.id)}
                  disabled={extractFreeMutation.isPending || extractAiMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium disabled:opacity-50 text-sm"
                >
                  {extractingProvider === provider.id ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Transcribing...
                    </>
                  ) : (
                    provider.name
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Download audio for local transcription */}
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center justify-center w-8 h-8 bg-gray-600 text-white text-xs font-bold rounded-lg">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              </span>
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-900">Download audio for local transcription</div>
                <div className="text-xs text-gray-500">
                  {audioProgress?.status === 'downloading' && audioProgress.current && audioProgress.total ? (
                    <>Downloading {audioProgress.current}/{audioProgress.total}: {audioProgress.title}</>
                  ) : audioProgress?.status === 'zipping' ? (
                    <>Creating ZIP file...</>
                  ) : audioProgress?.status === 'ready' ? (
                    <>Starting download...</>
                  ) : selectedPendingCount > 0 ? (
                    <>{selectedPendingCount} video{selectedPendingCount > 1 ? 's' : ''} selected</>
                  ) : (
                    <>Select videos below or download all</>
                  )}
                </div>
                {/* Progress bar */}
                {audioProgress?.status === 'downloading' && audioProgress.current && audioProgress.total && (
                  <div className="mt-2 w-full max-w-xs">
                    <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gray-600 rounded-full transition-all duration-300"
                        style={{ width: `${(audioProgress.current / audioProgress.total) * 100}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {audioProgress ? (
                <button
                  onClick={handleCancelDownload}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors font-medium text-sm"
                >
                  Cancel
                </button>
              ) : (
                <>
                  {/* Select All / Deselect All */}
                  {selectedPendingCount === 0 ? (
                    <button
                      onClick={handleSelectAll}
                      className="px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors text-sm"
                    >
                      Select All
                    </button>
                  ) : (
                    <button
                      onClick={handleDeselectAll}
                      className="px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors text-sm"
                    >
                      Deselect
                    </button>
                  )}
                  {/* Download button */}
                  <button
                    onClick={() => handleDownloadZip(selectedPendingCount > 0)}
                    disabled={extractFreeMutation.isPending || extractAiMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors font-medium disabled:opacity-50 text-sm"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    {selectedPendingCount > 0
                      ? `Download Selected (${selectedPendingCount})`
                      : 'Download All (ZIP)'
                    }
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Sorting, Filter and Search Toolbar */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search videos..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              />
            </div>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2">
            <select
              value={filterDefinition}
              onChange={(e) => setFilterDefinition(e.target.value as 'all' | 'hd' | 'sd')}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-sm"
            >
              <option value="all">All Quality</option>
              <option value="hd">HD Only</option>
              <option value="sd">SD Only</option>
            </select>
            <select
              value={filterCaption}
              onChange={(e) => setFilterCaption(e.target.value as 'all' | 'cc' | 'no-cc')}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-sm"
            >
              <option value="all">All Captions</option>
              <option value="cc">Has CC</option>
              <option value="no-cc">No CC</option>
            </select>
          </div>

          {/* Sort By */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortBy)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-sm"
            >
              <option value="published_at">Date</option>
              <option value="view_count">Views</option>
              <option value="like_count">Likes</option>
              <option value="duration_seconds">Duration</option>
              <option value="title">Title</option>
            </select>
            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="p-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
            >
              {sortOrder === 'asc' ? (
                <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
                </svg>
              ) : (
                <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Videos */}
      {videosLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-gray-200 rounded-xl animate-pulse"></div>
          ))}
        </div>
      ) : videos.length === 0 ? (
        <div className="text-center py-16 bg-gray-50 rounded-2xl border-2 border-dashed border-gray-200">
          <div className="text-gray-400 mb-4">
            {activeTab === 'extracted' ? (
              <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            ) : (
              <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {search ? 'No matching videos' :
              activeTab === 'pending' ? 'All done!' :
              'No transcripts yet'
            }
          </h3>
          <p className="text-gray-500">
            {search ? 'Try adjusting your search' :
              activeTab === 'pending' ? 'All videos have been transcribed' :
              'Extract transcripts from the Pending tab'
            }
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {videos.map((video) => (
            <VideoCard
              key={video.id}
              video={video}
              channelId={id!}
              onViewTranscript={setTranscriptVideoId}
              showCheckbox={activeTab === 'pending'}
              isSelected={selectedVideoIds.has(video.id)}
              onSelectChange={handleSelectVideo}
            />
          ))}
        </div>
      )}

      <TranscriptModal
        videoId={transcriptVideoId}
        onClose={() => setTranscriptVideoId(null)}
      />
    </div>
  );
}
