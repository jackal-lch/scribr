import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { addChannel, previewChannel } from '../api/channels';
import type { ChannelPreview } from '../api/channels';

interface AddChannelModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AddChannelModal({ isOpen, onClose }: AddChannelModalProps) {
  const [url, setUrl] = useState('');
  const [tags, setTags] = useState('');
  const [preview, setPreview] = useState<ChannelPreview | null>(null);
  const [error, setError] = useState('');
  const queryClient = useQueryClient();

  const previewMutation = useMutation({
    mutationFn: (channelUrl: string) => previewChannel(channelUrl),
    onSuccess: (data) => {
      setPreview(data);
      setError('');
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Could not find channel. Please check the URL.');
      setPreview(null);
    },
  });

  const addMutation = useMutation({
    mutationFn: () => addChannel({
      url,
      tags: tags.split(',').map(t => t.trim()).filter(t => t.length > 0),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] });
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      handleClose();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to add channel');
    },
  });

  const handleClose = () => {
    setUrl('');
    setTags('');
    setPreview(null);
    setError('');
    onClose();
  };

  const handlePreview = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    previewMutation.mutate(url.trim());
  };

  const handleAdd = () => {
    addMutation.mutate();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/50" onClick={handleClose} />

        <div className="relative bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-900">Add YouTube Channel</h2>
            <button
              onClick={handleClose}
              className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {!preview ? (
            <form onSubmit={handlePreview}>
              <div className="mb-4">
                <label htmlFor="channel-url" className="block text-sm font-medium text-gray-700 mb-2">
                  YouTube Channel URL
                </label>
                <input
                  type="text"
                  id="channel-url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://youtube.com/@channel or youtube.com/c/name"
                  className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                  autoFocus
                />
                <p className="mt-2 text-sm text-gray-500">
                  Supports @handles, /channel/, /c/, and /user/ URLs
                </p>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {error}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleClose}
                  className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!url.trim() || previewMutation.isPending}
                  className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {previewMutation.isPending ? 'Looking up...' : 'Find Channel'}
                </button>
              </div>
            </form>
          ) : (
            <div>
              <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl mb-4">
                {preview.thumbnail_url ? (
                  <img
                    src={preview.thumbnail_url}
                    alt={preview.channel_name}
                    className="w-16 h-16 rounded-full object-cover"
                  />
                ) : (
                  <div className="w-16 h-16 rounded-full bg-gray-200 flex items-center justify-center">
                    <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 truncate">{preview.channel_name}</h3>
                  <div className="flex items-center gap-2 text-sm">
                    <a
                      href={preview.channel_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800"
                    >
                      View on YouTube
                    </a>
                    {preview.total_videos && (
                      <span className="text-gray-500">• {preview.total_videos} videos</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Tags input */}
              <div className="mb-4">
                <label htmlFor="tags" className="block text-sm font-medium text-gray-700 mb-2">
                  Tags (optional)
                </label>
                <input
                  type="text"
                  id="tags"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="tech, science, tutorials"
                  className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                />
                <p className="mt-2 text-sm text-gray-500">
                  Separate tags with commas for easy filtering
                </p>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {error}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setPreview(null)}
                  className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors font-medium"
                >
                  Back
                </button>
                <button
                  onClick={handleAdd}
                  disabled={addMutation.isPending}
                  className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
                >
                  {addMutation.isPending ? 'Adding...' : 'Add Channel'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
