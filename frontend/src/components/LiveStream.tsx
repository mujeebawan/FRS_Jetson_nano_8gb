import { useEffect, useRef, useState } from 'react';
import { streamApi, systemApi, camerasApi } from '../services/api';
import { Play, Pause, RefreshCw, ZoomIn, ZoomOut, Maximize2, ChevronLeft, ChevronRight } from 'lucide-react';

interface Camera {
  id: number;
  name: string;
  ip_address: string;
  enabled: boolean;
}

interface LiveStreamProps {
  autoStart?: boolean;
  cameraId?: number;  // Optional: specific camera to display
}

export function LiveStream({ autoStart = true, cameraId }: LiveStreamProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [fps, setFps] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [cameraZoom, setCameraZoom] = useState(0);
  const [isZooming, setIsZooming] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(cameraId || null);

  // Load available cameras
  useEffect(() => {
    const loadCameras = async () => {
      try {
        const response = await camerasApi.list(true); // enabled only
        setCameras(response.data);
        // Set first camera as default if none selected
        if (!selectedCameraId && response.data.length > 0) {
          setSelectedCameraId(response.data[0].id);
        }
      } catch (err) {
        console.error('Failed to load cameras:', err);
      }
    };
    loadCameras();
  }, []);

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
    if (imgRef.current && selectedCameraId) {
      imgRef.current.src = `${streamApi.getCameraMjpegUrl(selectedCameraId)}?t=${Date.now()}`;
    }
  };

  // Get stream URL for current camera (with cache busting for camera switches)
  const getStreamUrl = () => {
    if (selectedCameraId) {
      return `${streamApi.getCameraMjpegUrl(selectedCameraId)}?cam=${selectedCameraId}`;
    }
    return streamApi.getMjpegUrl(); // Fallback to full view
  };

  // Navigate to next/previous camera
  const selectNextCamera = () => {
    if (cameras.length === 0) return;
    const currentIndex = cameras.findIndex(c => c.id === selectedCameraId);
    const nextIndex = (currentIndex + 1) % cameras.length;
    setSelectedCameraId(cameras[nextIndex].id);
  };

  const selectPrevCamera = () => {
    if (cameras.length === 0) return;
    const currentIndex = cameras.findIndex(c => c.id === selectedCameraId);
    const prevIndex = (currentIndex - 1 + cameras.length) % cameras.length;
    setSelectedCameraId(cameras[prevIndex].id);
  };

  const currentCamera = cameras.find(c => c.id === selectedCameraId);

  // Camera optical zoom controls (hold to zoom) - uses selected camera
  const startZoomIn = async () => {
    if (!selectedCameraId) return;
    setIsZooming(true);
    try {
      await systemApi.zoomIn(50, selectedCameraId);
    } catch (err) {
      console.error('Zoom in failed:', err);
    }
  };

  const startZoomOut = async () => {
    if (!selectedCameraId) return;
    setIsZooming(true);
    try {
      await systemApi.zoomOut(50, selectedCameraId);
    } catch (err) {
      console.error('Zoom out failed:', err);
    }
  };

  const stopZoom = async () => {
    setIsZooming(false);
    try {
      await systemApi.zoomStop(selectedCameraId || undefined);
      // Update zoom level display
      const status = await systemApi.ptzStatus(selectedCameraId || undefined);
      setCameraZoom(status.data.zoom || 0);
    } catch (err) {
      console.error('Zoom stop failed:', err);
    }
  };

  const resetZoom = async () => {
    if (!selectedCameraId) return;
    try {
      await systemApi.zoomSet(0, selectedCameraId);
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
        <h3>
          {cameras.length > 1 && (
            <button onClick={selectPrevCamera} className="camera-nav-btn" title="Previous Camera">
              <ChevronLeft size={18} />
            </button>
          )}
          <span className="camera-name">{currentCamera?.name || 'Live Stream'}</span>
          {cameras.length > 1 && (
            <button onClick={selectNextCamera} className="camera-nav-btn" title="Next Camera">
              <ChevronRight size={18} />
            </button>
          )}
        </h3>
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
            key={`stream-${selectedCameraId || 'all'}`}
            ref={imgRef}
            src={isPlaying ? getStreamUrl() : ''}
            alt={currentCamera?.name || 'Live Stream'}
            className="stream-image"
          />
        )}
      </div>
    </div>
  );
}

export default LiveStream;
