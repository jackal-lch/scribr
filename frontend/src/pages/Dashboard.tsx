import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getChannels, getAllTags } from '../api/channels';
import ChannelCard from '../components/ChannelCard';
import AddChannelModal from '../components/AddChannelModal';

export default function Dashboard() {
  const [isAddChannelOpen, setIsAddChannelOpen] = useState(false);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);

  const { data: channels = [], isLoading, error } = useQuery({
    queryKey: ['channels', selectedTag],
    queryFn: () => getChannels(selectedTag || undefined),
  });

  const { data: allTags = [] } = useQuery({
    queryKey: ['tags'],
    queryFn: getAllTags,
  });

  const totalVideos = channels.reduce((sum, ch) => sum + ch.video_count, 0);
  const totalOnYouTube = channels.reduce((sum, ch) => sum + (ch.total_videos || 0), 0);

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-48 mb-6"></div>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-xl"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">
          Failed to load channels. Please try again.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Channels</h1>
          <p className="text-gray-500 mt-1">
            {channels.length} channels • {totalVideos} videos fetched
            {totalOnYouTube > 0 && ` (${totalOnYouTube} total on YouTube)`}
          </p>
        </div>
        <button
          onClick={() => setIsAddChannelOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium shadow-sm"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Channel
        </button>
      </div>

      {/* Tag Filter */}
      {allTags.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-500">Filter:</span>
            <button
              onClick={() => setSelectedTag(null)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                selectedTag === null
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              All
            </button>
            {allTags.map((tag) => (
              <button
                key={tag}
                onClick={() => setSelectedTag(tag)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  selectedTag === tag
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Channel List */}
      {channels.length === 0 ? (
        <div className="text-center py-16 bg-gray-50 rounded-2xl border-2 border-dashed border-gray-200">
          <div className="text-gray-400 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {selectedTag ? `No channels with tag "${selectedTag}"` : 'No channels yet'}
          </h3>
          <p className="text-gray-500 mb-6">
            {selectedTag ? 'Try a different filter or add a new channel' : 'Add a YouTube channel to start tracking transcripts'}
          </p>
          <button
            onClick={() => setIsAddChannelOpen(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Your First Channel
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {channels.map((channel) => (
            <ChannelCard key={channel.id} channel={channel} />
          ))}
        </div>
      )}

      <AddChannelModal
        isOpen={isAddChannelOpen}
        onClose={() => setIsAddChannelOpen(false)}
      />
    </div>
  );
}
