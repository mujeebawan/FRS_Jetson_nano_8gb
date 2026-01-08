import { useEffect, useState, useCallback } from 'react';
import { camerasApi, streamApi } from '../services/api';
import { Grid, Maximize2, Video, VideoOff, RefreshCw, Check } from 'lucide-react';

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

  // Get camera snapshot URL
  const getCameraSnapshotUrl = (camera: Camera) => {
    return camerasApi.snapshot(camera.id);
  };

  // Calculate grid layout based on camera count
  const getGridClass = () => {
    const count = cameras.length;
    if (count <= 1) return 'grid-1x1';
    if (count <= 2) return 'grid-2x1';
    if (count <= 4) return 'grid-2x2';
    if (count <= 6) return 'grid-3x2';
    return 'grid-4x2';
  };

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

  // Fullscreen view
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
          {streamStatus?.running && activeCamera === fullscreenCamera.id ? (
            <img
              src={streamApi.getMjpegUrl()}
              alt={fullscreenCamera.name}
              className="stream-image"
            />
          ) : (
            <div className="stream-placeholder">
              <Video size={48} />
              <p>Connecting to {fullscreenCamera.name}...</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Grid view
  return (
    <div className="multi-camera-view">
      <div className="view-header">
        <h3>
          <Grid size={20} />
          Multi-Camera View
        </h3>
        <div className="view-controls">
          <span className="camera-count">{cameras.length} camera{cameras.length !== 1 ? 's' : ''}</span>
          <button onClick={loadData} title="Refresh cameras">
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      <div className={`camera-grid ${getGridClass()}`}>
        {cameras.map((camera) => (
          <div
            key={camera.id}
            className={`camera-tile ${camera.id === activeCamera ? 'active' : ''} ${switching && camera.id === activeCamera ? 'switching' : ''}`}
            onClick={() => switchCamera(camera)}
          >
            <div className="tile-header">
              <span className="camera-name">{camera.name}</span>
              {camera.id === activeCamera && (
                <span className="active-badge" title="Currently streaming">
                  <Check size={14} />
                  Live
                </span>
              )}
            </div>

            <div className="tile-preview">
              {camera.id === activeCamera && streamStatus?.running ? (
                <img
                  src={streamApi.getMjpegUrl()}
                  alt={camera.name}
                  className="preview-stream"
                />
              ) : (
                <img
                  src={getCameraSnapshotUrl(camera)}
                  alt={camera.name}
                  className="preview-snapshot"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              )}
              {switching && (
                <div className="switching-overlay">
                  <RefreshCw size={24} className="spin" />
                  Switching...
                </div>
              )}
            </div>

            <div className="tile-footer">
              <span className="camera-location">{camera.location || camera.ip_address}</span>
              <span className={`online-status ${camera.is_online ? 'online' : 'offline'}`}>
                {camera.is_online ? 'Online' : 'Offline'}
              </span>
              <button
                className="fullscreen-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  enterFullscreen(camera);
                }}
                title="Fullscreen"
              >
                <Maximize2 size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {activeCamera && streamStatus?.camera && (
        <div className="active-stream-info">
          <Video size={16} />
          <span>
            Streaming: <strong>{streamStatus.camera.name}</strong>
            {' '}({streamStatus.camera.stream_quality}) - {streamStatus.fps.toFixed(1)} FPS
          </span>
        </div>
      )}
    </div>
  );
}

export default MultiCameraView;
