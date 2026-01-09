import { useEffect, useState, useCallback } from 'react';
import { camerasApi, streamApi } from '../services/api';
import { Grid, Maximize2, Video, VideoOff, RefreshCw } from 'lucide-react';

interface Camera {
  id: number;
  name: string;
  ip_address: string;
  port: number;
  stream_quality: string;
  enabled: boolean;
  is_online: boolean;
  location?: string;
}

interface StreamStatus {
  running: boolean;
  fps: number;
  camera?: {
    id: number;
    name: string;
    ip_address: string;
    stream_quality: string;
  };
}

type ViewMode = 'grid' | 'fullscreen';

export function MultiCameraView() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [activeCamera, setActiveCamera] = useState<number | null>(null);
  const [streamStatus, setStreamStatus] = useState<StreamStatus | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [fullscreenCamera, setFullscreenCamera] = useState<Camera | null>(null);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load cameras and stream status
  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [camerasResponse, statusResponse] = await Promise.all([
        camerasApi.list(true), // Only enabled cameras
        streamApi.status()
      ]);

      setCameras(camerasResponse.data);
      setStreamStatus(statusResponse.data);

      // Set active camera from stream status
      if (statusResponse.data.camera) {
        setActiveCamera(statusResponse.data.camera.id);
      }
    } catch (err) {
      setError('Failed to load cameras');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();

    // Poll for updates
    const interval = setInterval(async () => {
      try {
        const statusResponse = await streamApi.status();
        setStreamStatus(statusResponse.data);
        if (statusResponse.data.camera) {
          setActiveCamera(statusResponse.data.camera.id);
        }
      } catch {
        // Ignore polling errors
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [loadData]);

  // Switch to a different camera
  const switchCamera = async (camera: Camera) => {
    if (switching || camera.id === activeCamera) return;

    setSwitching(true);
    try {
      await streamApi.switchCamera(camera.id);
      setActiveCamera(camera.id);

      // Update status
      const statusResponse = await streamApi.status();
      setStreamStatus(statusResponse.data);
    } catch (err) {
      console.error('Failed to switch camera:', err);
      setError('Failed to switch camera');
    } finally {
      setSwitching(false);
    }
  };

  // Enter fullscreen for a camera
  const enterFullscreen = (camera: Camera) => {
    setFullscreenCamera(camera);
    setViewMode('fullscreen');

    // If not already streaming this camera, switch to it
    if (camera.id !== activeCamera) {
      switchCamera(camera);
    }
  };

  // Exit fullscreen
  const exitFullscreen = () => {
    setFullscreenCamera(null);
    setViewMode('grid');
  };

  // Get camera snapshot URL (for future use)
  const _getCameraSnapshotUrl = (camera: Camera) => {
    return camerasApi.snapshot(camera.id);
  };

  // Calculate grid layout based on camera count (for future use)
  const _getGridClass = () => {
    const count = cameras.length;
    if (count <= 1) return 'grid-1x1';
    if (count <= 2) return 'grid-2x1';
    if (count <= 4) return 'grid-2x2';
    if (count <= 6) return 'grid-3x2';
    return 'grid-4x2';
  };

  // Suppress unused variable warnings
  void _getCameraSnapshotUrl;
  void _getGridClass;

  if (loading) {
    return (
      <div className="multi-camera-view loading">
        <div className="loading-spinner">Loading cameras...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="multi-camera-view error">
        <div className="error-message">{error}</div>
        <button onClick={loadData} className="retry-btn">
          <RefreshCw size={18} />
          Retry
        </button>
      </div>
    );
  }

  if (cameras.length === 0) {
    return (
      <div className="multi-camera-view empty">
        <VideoOff size={48} />
        <p>No cameras configured</p>
        <p className="hint">Add cameras in the Cameras tab</p>
      </div>
    );
  }

  // Fullscreen view - show single camera
  if (viewMode === 'fullscreen' && fullscreenCamera) {
    return (
      <div className="multi-camera-view fullscreen-mode">
        <div className="fullscreen-header">
          <h3>{fullscreenCamera.name}</h3>
          <div className="fullscreen-info">
            <span className="location">{fullscreenCamera.location || fullscreenCamera.ip_address}</span>
            <span className="quality">{fullscreenCamera.stream_quality.toUpperCase()}</span>
            {streamStatus?.running && (
              <span className="fps">FPS: {streamStatus.fps.toFixed(1)}</span>
            )}
          </div>
          <button onClick={exitFullscreen} className="exit-fullscreen-btn">
            <Grid size={20} />
            Grid View
          </button>
        </div>
        <div className="fullscreen-stream">
          <img
            key={`fullscreen-${fullscreenCamera.id}`}
            src={`${streamApi.getCameraMjpegUrl(fullscreenCamera.id)}?fs=1`}
            alt={fullscreenCamera.name}
            className="stream-image"
            style={{ width: '100%', height: 'auto', maxHeight: '80vh', objectFit: 'contain' }}
          />
        </div>
      </div>
    );
  }

  // Grid view - Show combined tiled stream from DeepStream
  return (
    <div className="multi-camera-view">
      <div className="view-header">
        <h3>
          <Grid size={20} />
          Multi-Camera View
        </h3>
        <div className="view-controls">
          <span className="camera-count">{cameras.length} camera{cameras.length !== 1 ? 's' : ''}</span>
          {streamStatus?.running && (
            <span className="fps-badge">{streamStatus.fps.toFixed(1)} FPS</span>
          )}
          <button onClick={loadData} title="Refresh cameras">
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      {/* Combined tiled stream - shows all cameras in one view */}
      <div className="combined-stream-container">
        <img
          src={`${streamApi.getMjpegUrl()}?multi=1`}
          alt="Multi-Camera Feed"
          className="combined-stream"
          style={{ width: '100%', height: 'auto', maxHeight: '75vh', objectFit: 'contain', background: '#1a1a2e' }}
        />
        <div className="camera-labels">
          {cameras.map((camera, index) => (
            <div
              key={camera.id}
              className={`camera-label ${index === 0 ? 'left' : 'right'}`}
              onClick={() => enterFullscreen(camera)}
            >
              <span className="label-name">{camera.name}</span>
              <span className={`online-status ${camera.is_online ? 'online' : 'offline'}`}>
                {camera.is_online ? 'Online' : 'Offline'}
              </span>
              <Maximize2 size={14} className="fullscreen-icon" />
            </div>
          ))}
        </div>
      </div>

      {streamStatus && (
        <div className="active-stream-info">
          <Video size={16} />
          <span>
            {streamStatus.running ? (
              <>Streaming: <strong>{cameras.length} cameras</strong> - {streamStatus.fps.toFixed(1)} FPS</>
            ) : (
              <>Stream starting...</>
            )}
          </span>
        </div>
      )}
    </div>
  );
}

export default MultiCameraView;
