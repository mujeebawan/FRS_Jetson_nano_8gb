import { useState, useEffect, useCallback } from 'react';
import { camerasApi } from '../services/api';
import {
  Camera,
  Plus,
  Edit2,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  Wifi,
  WifiOff,
  Save,
  X,
  Play,
  Eye,
  EyeOff,
  Image
} from 'lucide-react';

interface CameraData {
  id: number;
  name: string;
  ip_address: string;
  port: number;
  username: string;
  stream_quality: string;
  enabled: boolean;
  detection_enabled: boolean;
  detection_confidence: number | null;
  recognition_threshold: number | null;
  frame_skip: number | null;
  is_online: boolean;
  last_seen: string | null;
  current_fps: number | null;
  error_message: string | null;
  location: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
  display_status: string;
  quality_description: string;
}

interface StreamQualityOption {
  value: string;
  label: string;
  description: string;
}

interface CameraFormData {
  name: string;
  ip_address: string;
  port: number;
  username: string;
  password: string;
  stream_quality: string;
  enabled: boolean;
  detection_enabled: boolean;
  location: string;
  notes: string;
}

const defaultFormData: CameraFormData = {
  name: '',
  ip_address: '',
  port: 554,
  username: 'admin',
  password: '',
  stream_quality: 'third',
  enabled: true,
  detection_enabled: true,
  location: '',
  notes: '',
};

export function CameraList() {
  const [cameras, setCameras] = useState<CameraData[]>([]);
  const [loading, setLoading] = useState(true);
  const [qualityOptions, setQualityOptions] = useState<StreamQualityOption[]>([]);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingCamera, setEditingCamera] = useState<CameraData | null>(null);
  const [formData, setFormData] = useState<CameraFormData>(defaultFormData);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Testing state
  const [testingCameraId, setTestingCameraId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{ cameraId: number; success: boolean; message: string } | null>(null);

  // Snapshot preview
  const [previewCameraId, setPreviewCameraId] = useState<number | null>(null);

  // Load cameras
  const loadCameras = useCallback(async () => {
    try {
      const response = await camerasApi.list();
      setCameras(response.data);
    } catch (err) {
      console.error('Failed to load cameras:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load quality options
  const loadQualityOptions = useCallback(async () => {
    try {
      const response = await camerasApi.getQualityOptions();
      setQualityOptions(response.data);
    } catch (err) {
      console.error('Failed to load quality options:', err);
      // Fallback options
      setQualityOptions([
        { value: 'third', label: 'Low (480p)', description: 'Recommended for AI' },
        { value: 'sub', label: 'Medium (720p)', description: 'Balanced' },
        { value: 'main', label: 'High (4K/1080p)', description: 'Highest quality' },
      ]);
    }
  }, []);

  useEffect(() => {
    loadCameras();
    loadQualityOptions();
  }, [loadCameras, loadQualityOptions]);

  // Open form for new camera
  const handleAddCamera = () => {
    setEditingCamera(null);
    setFormData(defaultFormData);
    setFormError(null);
    setShowForm(true);
  };

  // Open form for editing
  const handleEditCamera = (camera: CameraData) => {
    setEditingCamera(camera);
    setFormData({
      name: camera.name,
      ip_address: camera.ip_address,
      port: camera.port,
      username: camera.username,
      password: '', // Don't show existing password
      stream_quality: camera.stream_quality,
      enabled: camera.enabled,
      detection_enabled: camera.detection_enabled,
      location: camera.location || '',
      notes: camera.notes || '',
    });
    setFormError(null);
    setShowForm(true);
  };

  // Close form
  const handleCloseForm = () => {
    setShowForm(false);
    setEditingCamera(null);
    setFormData(defaultFormData);
    setFormError(null);
  };

  // Save camera
  const handleSave = async () => {
    // Validation
    if (!formData.name.trim()) {
      setFormError('Camera name is required');
      return;
    }
    if (!formData.ip_address.trim()) {
      setFormError('IP address is required');
      return;
    }
    if (!formData.username.trim()) {
      setFormError('Username is required');
      return;
    }
    if (!editingCamera && !formData.password.trim()) {
      setFormError('Password is required for new cameras');
      return;
    }

    setSaving(true);
    setFormError(null);

    try {
      if (editingCamera) {
        // Update existing camera
        const updateData: any = {
          name: formData.name,
          ip_address: formData.ip_address,
          port: formData.port,
          username: formData.username,
          stream_quality: formData.stream_quality,
          enabled: formData.enabled,
          detection_enabled: formData.detection_enabled,
          location: formData.location || null,
          notes: formData.notes || null,
        };
        // Only include password if it was changed
        if (formData.password.trim()) {
          updateData.password = formData.password;
        }
        await camerasApi.update(editingCamera.id, updateData);
      } else {
        // Create new camera
        await camerasApi.create({
          name: formData.name,
          ip_address: formData.ip_address,
          port: formData.port,
          username: formData.username,
          password: formData.password,
          stream_quality: formData.stream_quality,
          enabled: formData.enabled,
          detection_enabled: formData.detection_enabled,
          location: formData.location || undefined,
          notes: formData.notes || undefined,
        });
      }

      handleCloseForm();
      await loadCameras();
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to save camera';
      setFormError(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  // Delete camera
  const handleDelete = async (camera: CameraData) => {
    if (!window.confirm(`Delete camera "${camera.name}"? This cannot be undone.`)) {
      return;
    }

    try {
      await camerasApi.delete(camera.id);
      await loadCameras();
    } catch (err) {
      console.error('Failed to delete camera:', err);
      alert('Failed to delete camera');
    }
  };

  // Test camera connection
  const handleTestConnection = async (cameraId: number) => {
    setTestingCameraId(cameraId);
    setTestResult(null);

    try {
      const response = await camerasApi.test(cameraId);
      setTestResult({
        cameraId,
        success: response.data.success,
        message: response.data.message + (response.data.resolution ? ` (${response.data.resolution})` : ''),
      });
      // Reload to update online status
      await loadCameras();
    } catch (err: any) {
      setTestResult({
        cameraId,
        success: false,
        message: err.response?.data?.detail || 'Connection test failed',
      });
    } finally {
      setTestingCameraId(null);
      // Clear result after 5 seconds
      setTimeout(() => setTestResult(null), 5000);
    }
  };

  // Toggle camera enabled/disabled
  const handleToggleEnabled = async (camera: CameraData) => {
    try {
      if (camera.enabled) {
        await camerasApi.disable(camera.id);
      } else {
        await camerasApi.enable(camera.id);
      }
      await loadCameras();
    } catch (err) {
      console.error('Failed to toggle camera:', err);
    }
  };

  // Get status color
  const getStatusColor = (camera: CameraData) => {
    if (!camera.enabled) return '#6b7280'; // gray
    if (camera.is_online) return '#10b981'; // green
    return '#ef4444'; // red
  };

  // Get status icon
  const StatusIcon = ({ camera }: { camera: CameraData }) => {
    if (!camera.enabled) return <EyeOff size={16} className="status-icon disabled" />;
    if (camera.is_online) return <Wifi size={16} className="status-icon online" />;
    return <WifiOff size={16} className="status-icon offline" />;
  };

  return (
    <div className="camera-list">
      <div className="camera-list-header">
        <h2>
          <Camera size={24} />
          Camera Management
        </h2>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={loadCameras} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spinning' : ''} />
            Refresh
          </button>
          <button className="btn btn-primary" onClick={handleAddCamera}>
            <Plus size={16} />
            Add Camera
          </button>
        </div>
      </div>

      {/* Camera Cards */}
      {loading ? (
        <div className="loading">Loading cameras...</div>
      ) : cameras.length === 0 ? (
        <div className="empty-state">
          <Camera size={48} />
          <h3>No Cameras Configured</h3>
          <p>Add your first camera to start monitoring.</p>
          <button className="btn btn-primary" onClick={handleAddCamera}>
            <Plus size={16} />
            Add Camera
          </button>
        </div>
      ) : (
        <div className="camera-grid">
          {cameras.map((camera) => (
            <div
              key={camera.id}
              className={`camera-card ${!camera.enabled ? 'disabled' : ''} ${camera.is_online ? 'online' : 'offline'}`}
            >
              <div className="camera-card-header">
                <div className="camera-status">
                  <StatusIcon camera={camera} />
                  <span
                    className="status-dot"
                    style={{ backgroundColor: getStatusColor(camera) }}
                  />
                </div>
                <h3>{camera.name}</h3>
                <div className="camera-actions">
                  <button
                    className="icon-btn"
                    onClick={() => handleEditCamera(camera)}
                    title="Edit"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    className="icon-btn danger"
                    onClick={() => handleDelete(camera)}
                    title="Delete"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              <div className="camera-card-body">
                <div className="camera-info">
                  <div className="info-row">
                    <span className="label">IP:</span>
                    <span className="value">{camera.ip_address}:{camera.port}</span>
                  </div>
                  <div className="info-row">
                    <span className="label">Quality:</span>
                    <span className="value">{camera.quality_description}</span>
                  </div>
                  <div className="info-row">
                    <span className="label">Status:</span>
                    <span className={`value status-${camera.display_status.toLowerCase()}`}>
                      {camera.display_status}
                    </span>
                  </div>
                  {camera.location && (
                    <div className="info-row">
                      <span className="label">Location:</span>
                      <span className="value">{camera.location}</span>
                    </div>
                  )}
                  {camera.current_fps !== null && camera.is_online && (
                    <div className="info-row">
                      <span className="label">FPS:</span>
                      <span className="value">{camera.current_fps.toFixed(1)}</span>
                    </div>
                  )}
                  {camera.error_message && !camera.is_online && (
                    <div className="info-row error">
                      <span className="label">Error:</span>
                      <span className="value">{camera.error_message}</span>
                    </div>
                  )}
                </div>

                {/* Test Result */}
                {testResult && testResult.cameraId === camera.id && (
                  <div className={`test-result ${testResult.success ? 'success' : 'error'}`}>
                    {testResult.success ? <CheckCircle size={16} /> : <XCircle size={16} />}
                    {testResult.message}
                  </div>
                )}
              </div>

              <div className="camera-card-footer">
                <button
                  className="btn btn-sm"
                  onClick={() => handleToggleEnabled(camera)}
                  title={camera.enabled ? 'Disable Camera' : 'Enable Camera'}
                >
                  {camera.enabled ? <EyeOff size={14} /> : <Eye size={14} />}
                  {camera.enabled ? 'Disable' : 'Enable'}
                </button>
                <button
                  className="btn btn-sm"
                  onClick={() => handleTestConnection(camera.id)}
                  disabled={testingCameraId === camera.id}
                  title="Test Connection"
                >
                  {testingCameraId === camera.id ? (
                    <RefreshCw size={14} className="spinning" />
                  ) : (
                    <Play size={14} />
                  )}
                  {testingCameraId === camera.id ? 'Testing...' : 'Test'}
                </button>
                <button
                  className="btn btn-sm"
                  onClick={() => setPreviewCameraId(previewCameraId === camera.id ? null : camera.id)}
                  title="Preview Snapshot"
                >
                  <Image size={14} />
                  Preview
                </button>
              </div>

              {/* Snapshot Preview */}
              {previewCameraId === camera.id && (
                <div className="snapshot-preview">
                  <img
                    src={camerasApi.snapshot(camera.id)}
                    alt={`${camera.name} preview`}
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit Camera Modal */}
      {showForm && (
        <div className="modal-overlay" onClick={handleCloseForm}>
          <div className="modal camera-form-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                <Camera size={20} />
                {editingCamera ? 'Edit Camera' : 'Add New Camera'}
              </h3>
              <button className="close-btn" onClick={handleCloseForm}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              {formError && (
                <div className="form-error">
                  <XCircle size={16} />
                  {formError}
                </div>
              )}

              <div className="form-grid">
                <div className="form-group">
                  <label>Camera Name *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., Front Gate"
                  />
                </div>

                <div className="form-group">
                  <label>Location</label>
                  <input
                    type="text"
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    placeholder="e.g., Main Entrance"
                  />
                </div>

                <div className="form-group">
                  <label>IP Address *</label>
                  <input
                    type="text"
                    value={formData.ip_address}
                    onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
                    placeholder="e.g., 192.168.1.70"
                  />
                </div>

                <div className="form-group">
                  <label>RTSP Port</label>
                  <input
                    type="number"
                    value={formData.port}
                    onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) || 554 })}
                    placeholder="554"
                  />
                </div>

                <div className="form-group">
                  <label>Username *</label>
                  <input
                    type="text"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    placeholder="admin"
                  />
                </div>

                <div className="form-group">
                  <label>Password {editingCamera ? '(leave blank to keep)' : '*'}</label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder={editingCamera ? '••••••••' : 'Enter password'}
                  />
                </div>

                <div className="form-group full-width">
                  <label>Stream Quality</label>
                  <div className="quality-options">
                    {qualityOptions.map((option) => (
                      <label
                        key={option.value}
                        className={`quality-option ${formData.stream_quality === option.value ? 'selected' : ''}`}
                      >
                        <input
                          type="radio"
                          name="stream_quality"
                          value={option.value}
                          checked={formData.stream_quality === option.value}
                          onChange={(e) => setFormData({ ...formData, stream_quality: e.target.value })}
                        />
                        <div className="quality-info">
                          <span className="quality-label">{option.label}</span>
                          <span className="quality-desc">{option.description}</span>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.enabled}
                      onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                    />
                    <span>Enabled (include in monitoring)</span>
                  </label>
                </div>

                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.detection_enabled}
                      onChange={(e) => setFormData({ ...formData, detection_enabled: e.target.checked })}
                    />
                    <span>Face Detection Enabled</span>
                  </label>
                </div>

                <div className="form-group full-width">
                  <label>Notes</label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    placeholder="Optional notes about this camera..."
                    rows={2}
                  />
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={handleCloseForm}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                <Save size={16} />
                {saving ? 'Saving...' : editingCamera ? 'Update Camera' : 'Add Camera'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CameraList;
