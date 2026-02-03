import { useState, useEffect, useRef } from 'react';
import { Outlet, Link } from 'react-router-dom';
import { Mic, Download, Check, ChevronDown, Loader2, Globe } from 'lucide-react';
import client from '../api/client';
import {
  getWhisperSettings,
  selectWhisperModel,
  downloadWhisperModel,
  formatModelSize,
} from '../api/whisper';
import type { WhisperSettings, DownloadProgress } from '../api/whisper';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

interface Settings {
  cookies_from_browser: string;
  valid_browsers: string[];
  whisper_model: string;
}

export default function Layout() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [whisperSettings, setWhisperSettings] = useState<WhisperSettings | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null);
  const [isWhisperUpdating, setIsWhisperUpdating] = useState(false);
  const cancelDownloadRef = useRef<(() => void) | null>(null);
  const [whisperDropdownOpen, setWhisperDropdownOpen] = useState(false);

  useEffect(() => {
    // Fetch current settings
    client.get('/settings')
      .then((res) => setSettings(res.data))
      .catch((err) => console.error('Failed to fetch settings:', err));
    // Fetch whisper settings
    getWhisperSettings()
      .then(setWhisperSettings)
      .catch((err) => console.error('Failed to fetch whisper settings:', err));
  }, []);

  // Clean up download on unmount
  useEffect(() => {
    return () => {
      if (cancelDownloadRef.current) {
        cancelDownloadRef.current();
      }
    };
  }, []);

  const handleBrowserChange = async (browser: string) => {
    if (!settings || isUpdating) return;

    setIsUpdating(true);
    try {
      await client.put('/settings/browser', { browser });
      setSettings({ ...settings, cookies_from_browser: browser });
    } catch (error) {
      console.error('Failed to update browser setting:', error);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleWhisperModelChange = async (modelName: string) => {
    if (!whisperSettings || isWhisperUpdating || downloadProgress) return;

    const model = whisperSettings.models.find((m) => m.name === modelName);
    if (!model) return;

    if (model.installed) {
      // Model is installed, select it
      setIsWhisperUpdating(true);
      try {
        await selectWhisperModel(modelName);
        setWhisperSettings({
          ...whisperSettings,
          selected_model: modelName,
        });
        setWhisperDropdownOpen(false);
      } catch (error) {
        console.error('Failed to select model:', error);
      } finally {
        setIsWhisperUpdating(false);
      }
    } else {
      // Model not installed, download it
      setDownloadProgress({ status: 'downloading', percent: 0, model: modelName });

      const cancel = downloadWhisperModel(
        modelName,
        (progress) => {
          setDownloadProgress(progress);
        },
        async () => {
          // Download complete - refresh settings and select model
          setDownloadProgress(null);
          cancelDownloadRef.current = null;

          try {
            const newSettings = await getWhisperSettings();
            setWhisperSettings(newSettings);
            // Auto-select the downloaded model
            await selectWhisperModel(modelName);
            setWhisperSettings({
              ...newSettings,
              selected_model: modelName,
              models: newSettings.models.map((m) =>
                m.name === modelName ? { ...m, installed: true } : m
              ),
            });
            setWhisperDropdownOpen(false);
          } catch (error) {
            console.error('Failed to select model after download:', error);
          }
        },
        (error) => {
          console.error('Download failed:', error);
          setDownloadProgress(null);
          cancelDownloadRef.current = null;
          alert(`Failed to download model: ${error}`);
        }
      );

      cancelDownloadRef.current = cancel;
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="flex items-center">
                <img src="/logo.png" alt="Scribr" className="h-8" />
              </Link>
            </div>
            <div className="flex items-center gap-3">
              {/* Whisper Model Selector */}
              {downloadProgress ? (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-md">
                  <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                  <div className="flex items-center gap-2 min-w-[120px]">
                    <div className="flex-1 h-1.5 bg-blue-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-600 transition-all duration-300"
                        style={{ width: `${downloadProgress.percent}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-blue-700 w-8">
                      {downloadProgress.percent}%
                    </span>
                  </div>
                </div>
              ) : whisperSettings ? (
                <Popover open={whisperDropdownOpen} onOpenChange={setWhisperDropdownOpen}>
                  <PopoverTrigger asChild>
                    <button
                      disabled={isWhisperUpdating}
                      className="flex items-center gap-2 px-3 h-8 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-md transition-colors disabled:opacity-50"
                    >
                      <Mic className="w-4 h-4 text-gray-500" />
                      <span className="text-sm font-medium text-gray-700">
                        {whisperSettings.selected_model}
                      </span>
                      {whisperSettings.models.find(m => m.name === whisperSettings.selected_model)?.installed ? (
                        <Check className="w-3.5 h-3.5 text-green-600" />
                      ) : (
                        <Download className="w-3.5 h-3.5 text-orange-500" />
                      )}
                      <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${whisperDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent align="end" className="w-64 p-0">
                    <div className="px-3 py-2 border-b border-gray-100">
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                        Whisper Model
                        <span className="ml-2 px-1.5 py-0.5 bg-gray-100 rounded text-gray-600 normal-case text-xs">
                          {whisperSettings.backend === 'mlx' ? 'MLX' : 'CPU'}
                        </span>
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        Local transcription model for converting audio to text
                      </p>
                    </div>
                    <div className="py-1">
                      {whisperSettings.models.map((model) => (
                        <button
                          key={model.name}
                          onClick={() => handleWhisperModelChange(model.name)}
                          className={`w-full flex items-center justify-between px-3 py-2 text-left hover:bg-gray-50 transition-colors ${
                            model.name === whisperSettings.selected_model ? 'bg-blue-50' : ''
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span className={`text-sm font-medium ${model.name === whisperSettings.selected_model ? 'text-blue-700' : 'text-gray-700'}`}>
                              {model.name}
                            </span>
                            <span className="text-xs text-gray-400">
                              {formatModelSize(model.size_mb)}
                            </span>
                          </div>
                          {model.installed ? (
                            <Check className="w-4 h-4 text-green-600" />
                          ) : (
                            <Download className="w-4 h-4 text-gray-400" />
                          )}
                        </button>
                      ))}
                    </div>
                    <div className="px-3 py-2 border-t border-gray-100">
                      <p className="text-xs text-gray-400">
                        {whisperSettings.models.filter(m => m.installed).length === 0
                          ? 'Click a model to download'
                          : `${whisperSettings.models.filter(m => m.installed).length} installed`}
                        {' · '}
                        {whisperSettings.backend === 'mlx' ? 'Apple Silicon' : 'CPU mode'}
                      </p>
                    </div>
                  </PopoverContent>
                </Popover>
              ) : (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-md">
                  <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                  <span className="text-sm text-gray-400">Loading...</span>
                </div>
              )}

              {/* Browser Cookies Selector */}
              {settings ? (
                <Popover>
                  <PopoverTrigger asChild>
                    <button
                      disabled={isUpdating}
                      className="flex items-center gap-2 px-3 h-8 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-md transition-colors disabled:opacity-50"
                    >
                      <Globe className="w-4 h-4 text-gray-500" />
                      <span className="text-sm font-medium text-gray-700">
                        {settings.cookies_from_browser.charAt(0).toUpperCase() + settings.cookies_from_browser.slice(1)}
                      </span>
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent align="end" className="w-48 p-0">
                    <div className="px-3 py-2 border-b border-gray-100">
                      <p className="text-xs text-gray-500">
                        Browser cookies for YouTube sign-in
                      </p>
                    </div>
                    <div className="py-1">
                      {settings.valid_browsers.map((browser) => (
                        <button
                          key={browser}
                          onClick={() => handleBrowserChange(browser)}
                          className={`w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors ${
                            browser === settings.cookies_from_browser ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                          }`}
                        >
                          {browser.charAt(0).toUpperCase() + browser.slice(1)}
                          {browser === settings.cookies_from_browser && (
                            <Check className="w-4 h-4 text-blue-600" />
                          )}
                        </button>
                      ))}
                    </div>
                  </PopoverContent>
                </Popover>
              ) : (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-md">
                  <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                  <span className="text-sm text-gray-400">Loading...</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
