import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getVideo, getTranscript } from '../api/videos';

interface TranscriptModalProps {
  videoId: string | null;
  onClose: () => void;
}

export default function TranscriptModal({ videoId, onClose }: TranscriptModalProps) {
  const [showTimestamps, setShowTimestamps] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: video } = useQuery({
    queryKey: ['video', videoId],
    queryFn: () => getVideo(videoId!),
    enabled: !!videoId,
  });

  const { data: transcript, isLoading, error } = useQuery({
    queryKey: ['transcript', videoId],
    queryFn: () => getTranscript(videoId!),
    enabled: !!videoId,
  });

  if (!videoId) return null;

  const displayContent = showTimestamps ? transcript?.content : transcript?.plain_content;

  const handleDownload = () => {
    if (!transcript || !video) return;

    const content = `Title: ${video.title}
Channel: ${video.channel_name}
Video URL: https://www.youtube.com/watch?v=${video.youtube_video_id}
Word Count: ${transcript.word_count}
Language: ${transcript.language}

---

${displayContent}`;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const suffix = showTimestamps ? '_timestamped' : '';
    a.download = `${video.title.slice(0, 50).replace(/[^a-zA-Z0-9 -_]/g, '')}${suffix}_transcript.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    if (!displayContent) return;
    try {
      await navigator.clipboard.writeText(displayContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/50" onClick={onClose} />

        <div className="relative bg-white rounded-2xl shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b">
            <div className="min-w-0 flex-1 pr-4">
              <h2 className="text-xl font-semibold text-gray-900 truncate">
                {video?.title || 'Loading...'}
              </h2>
              {video && (
                <p className="text-sm text-gray-500 mt-1">
                  {video.channel_name} • {transcript?.word_count?.toLocaleString()} words
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Toggle - only show if transcript has timestamps (caption method) */}
          {transcript && video?.transcript_method === 'caption' && (
            <div className="px-6 py-3 border-b bg-gray-50">
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium text-gray-700">Format:</span>
                <div className="flex rounded-lg bg-gray-200 p-1">
                  <button
                    onClick={() => setShowTimestamps(false)}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                      !showTimestamps
                        ? 'bg-white text-gray-900 shadow-sm'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Plain Text
                  </button>
                  <button
                    onClick={() => setShowTimestamps(true)}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                      showTimestamps
                        ? 'bg-white text-gray-900 shadow-sm'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    With Timestamps
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <svg className="w-8 h-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
            ) : error ? (
              <div className="text-center py-12">
                <p className="text-red-600">Failed to load transcript</p>
              </div>
            ) : transcript ? (
              <pre className="whitespace-pre-wrap font-mono text-sm text-gray-700 leading-relaxed">
                {displayContent}
              </pre>
            ) : null}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t bg-gray-50">
            <button
              onClick={handleCopy}
              disabled={!transcript}
              className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-50 ${
                copied
                  ? 'text-green-700 bg-green-50 border border-green-300'
                  : 'text-gray-700 bg-white border border-gray-300 hover:bg-gray-50'
              }`}
            >
              {copied ? (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Copied!
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy
                </>
              )}
            </button>
            <button
              onClick={handleDownload}
              disabled={!transcript}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
