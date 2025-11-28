import { useEffect, useRef, useState } from 'react';
import { streamApi } from '../services/api';
import { Play, Pause, RefreshCw } from 'lucide-react';

interface LiveStreamProps {
  autoStart?: boolean;
}

export function LiveStream({ autoStart = true }: LiveStreamProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [fps, setFps] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (autoStart) {
      startStream();
    }
    return () => {
      stopStream();
    };
  }, [autoStart]);

  const startStream = async () => {
    try {
      setError(null);
      await streamApi.start();
      setIsPlaying(true);

      // Poll for FPS updates
      const interval = setInterval(async () => {
        try {
          const response = await streamApi.status();
          setFps(response.data.fps || 0);
        } catch {
          // Ignore polling errors
        }
      }, 2000);

      return () => clearInterval(interval);
    } catch (err) {
      setError('Failed to start stream');
      console.error(err);
    }
  };

  const stopStream = async () => {
    try {
      await streamApi.stop();
      setIsPlaying(false);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleStream = () => {
    if (isPlaying) {
      stopStream();
    } else {
      startStream();
    }
  };

  const refreshStream = () => {
    if (imgRef.current) {
      imgRef.current.src = `${streamApi.getMjpegUrl()}?t=${Date.now()}`;
    }
  };

  return (
    <div className="stream-container">
      <div className="stream-header">
        <h3>Live Stream</h3>
        <div className="stream-controls">
          <span className="fps-display">FPS: {fps.toFixed(1)}</span>
          <button onClick={toggleStream} title={isPlaying ? 'Stop' : 'Start'}>
            {isPlaying ? <Pause size={20} /> : <Play size={20} />}
          </button>
          <button onClick={refreshStream} title="Refresh">
            <RefreshCw size={20} />
          </button>
        </div>
      </div>

      <div className="stream-video">
        {error ? (
          <div className="stream-error">{error}</div>
        ) : (
          <img
            ref={imgRef}
            src={isPlaying ? streamApi.getMjpegUrl() : ''}
            alt="Live Stream"
            style={{ width: '100%', height: 'auto', backgroundColor: '#000' }}
          />
        )}
      </div>
    </div>
  );
}

export default LiveStream;
