import { useEffect, useRef, useState } from 'react';
import { streamApi, systemApi } from '../services/api';
import { Play, Pause, RefreshCw, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

interface LiveStreamProps {
  autoStart?: boolean;
}

export function LiveStream({ autoStart = true }: LiveStreamProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [fps, setFps] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [cameraZoom, setCameraZoom] = useState(0);
  const [isZooming, setIsZooming] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    if (autoStart) {
      startStream();
    }
    return () => {
      stopStream();
    };
  }, [autoStart]);

  // Handle fullscreen change
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

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

  // Camera optical zoom controls (hold to zoom)
  const startZoomIn = async () => {
    setIsZooming(true);
    try {
      await systemApi.zoomIn(50);
    } catch (err) {
      console.error('Zoom in failed:', err);
    }
  };

  const startZoomOut = async () => {
    setIsZooming(true);
    try {
      await systemApi.zoomOut(50);
    } catch (err) {
      console.error('Zoom out failed:', err);
    }
  };

  const stopZoom = async () => {
    setIsZooming(false);
    try {
      await systemApi.zoomStop();
      // Update zoom level display
      const status = await systemApi.ptzStatus();
      setCameraZoom(status.data.zoom || 0);
    } catch (err) {
      console.error('Zoom stop failed:', err);
    }
  };

  const resetZoom = async () => {
    try {
      await systemApi.zoomSet(0);
      setCameraZoom(0);
    } catch (err) {
      console.error('Reset zoom failed:', err);
    }
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;

    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  };

  return (
    <div className={`stream-container ${isFullscreen ? 'fullscreen' : ''}`} ref={containerRef}>
      <div className="stream-header">
        <h3>Live Stream</h3>
        <div className="stream-controls">
          <span className="fps-display">FPS: {fps.toFixed(1)}</span>
          <span className="zoom-display" title="Camera optical zoom">{cameraZoom}%</span>
          <button
            onMouseDown={startZoomOut}
            onMouseUp={stopZoom}
            onMouseLeave={stopZoom}
            onTouchStart={startZoomOut}
            onTouchEnd={stopZoom}
            title="Zoom Out (hold)"
            className={isZooming ? 'active' : ''}
          >
            <ZoomOut size={20} />
          </button>
          <button
            onMouseDown={startZoomIn}
            onMouseUp={stopZoom}
            onMouseLeave={stopZoom}
            onTouchStart={startZoomIn}
            onTouchEnd={stopZoom}
            title="Zoom In (hold)"
            className={isZooming ? 'active' : ''}
          >
            <ZoomIn size={20} />
          </button>
          <button onClick={resetZoom} title="Reset Zoom" className={cameraZoom > 0 ? 'active' : ''}>
            1x
          </button>
          <button onClick={toggleFullscreen} title="Fullscreen">
            <Maximize2 size={20} />
          </button>
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
            className="stream-image"
          />
        )}
      </div>
    </div>
  );
}

export default LiveStream;
