import { useEffect, useState } from 'react';
import { systemApi } from '../services/api';
import { Activity, Camera, Users, Settings } from 'lucide-react';

interface SystemStatusData {
  stream: {
    running: boolean;
    fps: number;
    subscribers: number;
  };
  recognition: {
    persons: number;
    embeddings: number;
    threshold: number;
  };
  camera: {
    ip: string;
    model: string;
    connected: boolean;
  };
  settings: {
    detection_confidence: number;
    frame_skip: number;
    motion_trigger: boolean;
  };
}

export function SystemStatus() {
  const [status, setStatus] = useState<SystemStatusData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
    try {
      const response = await systemApi.status();
      setStatus(response.data);
    } catch (err) {
      console.error('Failed to load status:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !status) {
    return <div className="system-status loading">Loading status...</div>;
  }

  return (
    <div className="system-status">
      <h3>System Status</h3>

      <div className="status-grid">
        {/* Stream Status */}
        <div className="status-card">
          <div className="status-icon">
            <Activity size={24} />
          </div>
          <div className="status-content">
            <h4>Stream</h4>
            <div className={`status-indicator ${status.stream.running ? 'active' : 'inactive'}`}>
              {status.stream.running ? 'Running' : 'Stopped'}
            </div>
            <div className="status-details">
              <span>FPS: {status.stream.fps.toFixed(1)}</span>
              <span>Viewers: {status.stream.subscribers}</span>
            </div>
          </div>
        </div>

        {/* Camera Status */}
        <div className="status-card">
          <div className="status-icon">
            <Camera size={24} />
          </div>
          <div className="status-content">
            <h4>Camera</h4>
            <div className={`status-indicator ${status.camera.connected ? 'active' : 'inactive'}`}>
              {status.camera.connected ? 'Connected' : 'Disconnected'}
            </div>
            <div className="status-details">
              <span>{status.camera.model}</span>
              <span>{status.camera.ip}</span>
            </div>
          </div>
        </div>

        {/* Recognition Status */}
        <div className="status-card">
          <div className="status-icon">
            <Users size={24} />
          </div>
          <div className="status-content">
            <h4>Recognition</h4>
            <div className="status-details">
              <span>Persons: {status.recognition.persons}</span>
              <span>Embeddings: {status.recognition.embeddings}</span>
              <span>Threshold: {status.recognition.threshold}</span>
            </div>
          </div>
        </div>

        {/* Settings Status */}
        <div className="status-card">
          <div className="status-icon">
            <Settings size={24} />
          </div>
          <div className="status-content">
            <h4>Settings</h4>
            <div className="status-details">
              <span>Detection: {status.settings.detection_confidence}</span>
              <span>Frame Skip: {status.settings.frame_skip}</span>
              <span>Motion: {status.settings.motion_trigger ? 'On' : 'Off'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SystemStatus;
