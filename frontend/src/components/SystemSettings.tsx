import { useEffect, useState, useCallback } from 'react';
import { systemApi } from '../services/api';
import {
  Cpu,
  HardDrive,
  Thermometer,
  Zap,
  Settings,
  Save,
  RotateCcw,
  Activity,
  Eye,
  Layers,
  RefreshCw,
  Video,
  Trash2,
  AlertTriangle,
  Database
} from 'lucide-react';

interface ResourceStats {
  cpu: {
    percent: number;
    cores: number;
    load_1m: number;
  };
  memory: {
    used_mb: number;
    total_mb: number;
    percent: number;
    available_mb: number;
  };
  gpu: {
    percent: number;
    freq_mhz: number;
    memory_used_mb: number;
    memory_total_mb: number;
    temp_c?: number;
  };
  temperature: {
    cpu: number;
    gpu: number;
  };
  power: {
    watts: number;
  };
}

interface SettingsData {
  detection_confidence: number;
  recognition_threshold: number;
  frame_skip: number;
  enable_motion_trigger: boolean;
  alert_cooldown_seconds: number;
  detection_model: string;
  recognition_model: string;
  video_recording_enabled: boolean;
  video_clip_duration: number;
  ranges: {
    detection_confidence: { min: number; max: number; step: number; default: number };
    recognition_threshold: { min: number; max: number; step: number; default: number };
    frame_skip: { min: number; max: number; step: number; default: number };
    alert_cooldown_seconds: { min: number; max: number; step: number; default: number };
    video_clip_duration: { min: number; max: number; step: number; default: number };
  };
}

interface StorageData {
  disk: {
    total_gb: number;
    used_gb: number;
    free_gb: number;
    percent_used: number;
  };
  alerts_data: {
    size_mb: number;
    size_gb: number;
    snapshots: number;
    videos: number;
    date_folders: number;
  };
  warning: boolean;
  warning_threshold: number;
  message: string | null;
}

interface ModelPack {
  id: string;
  name: string;
  size_mb: number;
  fps_estimate: string;
  accuracy: string;
  description: string;
  detection: string;
  recognition: string;
  fp16_available: boolean;
  fp32_available: boolean;
  available: boolean;
}

interface ModelsData {
  packs: ModelPack[];
  current: {
    model: string;
    using_fp16: boolean;
    full_name: string;
  };
}

export function SystemSettings() {
  // State for resources
  const [resources, setResources] = useState<ResourceStats | null>(null);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [resourcesError, setResourcesError] = useState<string | null>(null);

  // State for settings
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [pendingSettings, setPendingSettings] = useState<Partial<SettingsData>>({});
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // State for models
  const [models, setModels] = useState<ModelsData | null>(null);
  const [changingModel, setChangingModel] = useState(false);
  const [modelMessage, setModelMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // State for storage
  const [storage, setStorage] = useState<StorageData | null>(null);
  const [cleaningUp, setCleaningUp] = useState(false);
  const [cleanupDays, setCleanupDays] = useState(30);
  const [storageMessage, setStorageMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Load resources periodically
  const loadResources = useCallback(async () => {
    try {
      const response = await systemApi.resources();
      setResources(response.data);
      setResourcesError(null);
    } catch (err) {
      setResourcesError('Failed to load resources');
      console.error('Resource load error:', err);
    } finally {
      setResourcesLoading(false);
    }
  }, []);

  // Load settings
  const loadSettings = useCallback(async () => {
    try {
      const response = await systemApi.getSettings();
      setSettings(response.data);
      setPendingSettings({});
    } catch (err) {
      console.error('Settings load error:', err);
    } finally {
      setSettingsLoading(false);
    }
  }, []);

  // Load models
  const loadModels = useCallback(async () => {
    try {
      const response = await systemApi.getModels();
      setModels(response.data);
    } catch (err) {
      console.error('Models load error:', err);
    }
  }, []);

  // Load storage
  const loadStorage = useCallback(async () => {
    try {
      const response = await systemApi.storage();
      setStorage(response.data);
    } catch (err) {
      console.error('Storage load error:', err);
    }
  }, []);

  // Cleanup old data
  const handleCleanup = async () => {
    if (!window.confirm(`Delete all alert data older than ${cleanupDays} days? This cannot be undone.`)) {
      return;
    }

    setCleaningUp(true);
    setStorageMessage(null);

    try {
      const response = await systemApi.cleanupStorage(cleanupDays);
      if (response.data.success) {
        setStorageMessage({
          type: 'success',
          text: response.data.message
        });
        // Reload storage stats
        await loadStorage();
      } else {
        setStorageMessage({
          type: 'error',
          text: 'Failed to cleanup storage'
        });
      }
    } catch (err) {
      setStorageMessage({ type: 'error', text: 'Failed to cleanup storage' });
      console.error('Cleanup error:', err);
    } finally {
      setCleaningUp(false);
      setTimeout(() => setStorageMessage(null), 5000);
    }
  };

  // Initial load
  useEffect(() => {
    loadResources();
    loadSettings();
    loadModels();
    loadStorage();

    // Refresh resources every 2 seconds
    const resourceInterval = setInterval(loadResources, 2000);
    // Refresh storage every 30 seconds
    const storageInterval = setInterval(loadStorage, 30000);

    return () => {
      clearInterval(resourceInterval);
      clearInterval(storageInterval);
    };
  }, [loadResources, loadSettings, loadModels, loadStorage]);

  // Handle setting change
  const handleSettingChange = (key: keyof SettingsData, value: number | boolean) => {
    setPendingSettings(prev => ({ ...prev, [key]: value }));
  };

  // Get current value (pending or saved)
  const getCurrentValue = <K extends keyof SettingsData>(key: K): SettingsData[K] | undefined => {
    if (pendingSettings[key] !== undefined) {
      return pendingSettings[key] as SettingsData[K];
    }
    return settings?.[key];
  };

  // Check if there are unsaved changes
  const hasChanges = Object.keys(pendingSettings).length > 0;

  // Save settings
  const saveSettings = async () => {
    if (!hasChanges) return;

    setSaving(true);
    setSaveMessage(null);

    try {
      const response = await systemApi.updateSettings({
        detection_confidence: pendingSettings.detection_confidence,
        recognition_threshold: pendingSettings.recognition_threshold,
        frame_skip: pendingSettings.frame_skip,
        enable_motion_trigger: pendingSettings.enable_motion_trigger,
        alert_cooldown_seconds: pendingSettings.alert_cooldown_seconds,
        video_recording_enabled: pendingSettings.video_recording_enabled,
        video_clip_duration: pendingSettings.video_clip_duration,
      });

      if (response.data.success) {
        setSaveMessage({ type: 'success', text: 'Settings applied successfully!' });
        // Reload settings to get updated values
        await loadSettings();
      } else {
        setSaveMessage({ type: 'error', text: response.data.errors?.join(', ') || 'Failed to apply settings' });
      }
    } catch (err) {
      setSaveMessage({ type: 'error', text: 'Failed to save settings' });
      console.error('Save error:', err);
    } finally {
      setSaving(false);
      // Clear message after 3 seconds
      setTimeout(() => setSaveMessage(null), 3000);
    }
  };

  // Reset to defaults
  const resetToDefaults = () => {
    if (!settings?.ranges) return;
    setPendingSettings({
      detection_confidence: settings.ranges.detection_confidence.default,
      recognition_threshold: settings.ranges.recognition_threshold.default,
      frame_skip: settings.ranges.frame_skip.default,
    });
  };

  // Discard changes
  const discardChanges = () => {
    setPendingSettings({});
  };

  // Change model
  const handleModelChange = async (modelId: string) => {
    if (!models || models.current.model === modelId) return;

    setChangingModel(true);
    setModelMessage(null);

    try {
      const response = await systemApi.changeModel(modelId, true);
      if (response.data.success) {
        setModelMessage({
          type: 'success',
          text: `Switched to ${response.data.model}. Stream restarting...`
        });
        // Reload models to update current selection
        await loadModels();
      } else {
        setModelMessage({
          type: 'error',
          text: response.data.error || 'Failed to change model'
        });
      }
    } catch (err) {
      setModelMessage({ type: 'error', text: 'Failed to change model' });
      console.error('Model change error:', err);
    } finally {
      setChangingModel(false);
      // Clear message after 5 seconds
      setTimeout(() => setModelMessage(null), 5000);
    }
  };

  // Progress bar component
  const ProgressBar = ({ value, max, color }: { value: number; max: number; color: string }) => {
    const percent = Math.min(100, (value / max) * 100);
    return (
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{
            width: `${percent}%`,
            backgroundColor: color
          }}
        />
      </div>
    );
  };

  // Get color based on value
  const getUsageColor = (percent: number) => {
    if (percent < 50) return '#10b981'; // green
    if (percent < 80) return '#f59e0b'; // yellow
    return '#ef4444'; // red
  };

  return (
    <div className="system-settings">
      {/* Resource Monitoring Section */}
      <section className="settings-section">
        <h3>
          <Activity size={20} />
          System Resources
          <button className="refresh-btn" onClick={loadResources} title="Refresh">
            <RefreshCw size={16} />
          </button>
        </h3>

        {resourcesError && (
          <div className="error-message">{resourcesError}</div>
        )}

        {resourcesLoading && !resources ? (
          <div className="loading">Loading resources...</div>
        ) : resources ? (
          <div className="resource-grid">
            {/* CPU */}
            <div className="resource-card">
              <div className="resource-header">
                <Cpu size={20} />
                <span>CPU</span>
              </div>
              <div className="resource-value">{resources.cpu.percent.toFixed(1)}%</div>
              <ProgressBar
                value={resources.cpu.percent}
                max={100}
                color={getUsageColor(resources.cpu.percent)}
              />
              <div className="resource-details">
                <span>Cores: {resources.cpu.cores}</span>
                <span>Load: {resources.cpu.load_1m?.toFixed(2)}</span>
              </div>
            </div>

            {/* Memory */}
            <div className="resource-card">
              <div className="resource-header">
                <HardDrive size={20} />
                <span>Memory</span>
              </div>
              <div className="resource-value">{resources.memory.percent.toFixed(1)}%</div>
              <ProgressBar
                value={resources.memory.percent}
                max={100}
                color={getUsageColor(resources.memory.percent)}
              />
              <div className="resource-details">
                <span>{resources.memory.used_mb}MB / {resources.memory.total_mb}MB</span>
              </div>
            </div>

            {/* GPU */}
            <div className="resource-card">
              <div className="resource-header">
                <Layers size={20} />
                <span>GPU</span>
              </div>
              <div className="resource-value">{resources.gpu.percent}%</div>
              <ProgressBar
                value={resources.gpu.percent}
                max={100}
                color={getUsageColor(resources.gpu.percent)}
              />
              <div className="resource-details">
                <span>{resources.gpu.freq_mhz} MHz</span>
                {resources.gpu.memory_used_mb > 0 && (
                  <span>{resources.gpu.memory_used_mb}MB used</span>
                )}
              </div>
            </div>

            {/* Temperature */}
            <div className="resource-card">
              <div className="resource-header">
                <Thermometer size={20} />
                <span>Temperature</span>
              </div>
              <div className="resource-value">
                {Math.max(resources.temperature.cpu, resources.temperature.gpu, resources.gpu.temp_c || 0).toFixed(0)}C
              </div>
              <div className="resource-details">
                <span>CPU: {resources.temperature.cpu.toFixed(1)}C</span>
                <span>GPU: {(resources.gpu.temp_c || resources.temperature.gpu).toFixed(1)}C</span>
              </div>
            </div>

            {/* Power */}
            {resources.power.watts > 0 && (
              <div className="resource-card">
                <div className="resource-header">
                  <Zap size={20} />
                  <span>Power</span>
                </div>
                <div className="resource-value">{resources.power.watts.toFixed(1)}W</div>
              </div>
            )}
          </div>
        ) : null}
      </section>

      {/* Detection & Recognition Settings */}
      <section className="settings-section">
        <h3>
          <Eye size={20} />
          Detection & Recognition
        </h3>

        {settingsLoading ? (
          <div className="loading">Loading settings...</div>
        ) : settings ? (
          <div className="settings-form">
            {/* Detection Confidence */}
            <div className="setting-row">
              <div className="setting-label">
                <span>Detection Confidence</span>
                <span className="setting-hint">Minimum score to detect a face (higher = fewer false positives)</span>
              </div>
              <div className="setting-control">
                <input
                  type="range"
                  min={settings.ranges.detection_confidence.min}
                  max={settings.ranges.detection_confidence.max}
                  step={settings.ranges.detection_confidence.step}
                  value={getCurrentValue('detection_confidence') || settings.detection_confidence}
                  onChange={(e) => handleSettingChange('detection_confidence', parseFloat(e.target.value))}
                />
                <span className="setting-value">
                  {(getCurrentValue('detection_confidence') || settings.detection_confidence).toFixed(2)}
                </span>
              </div>
            </div>

            {/* Recognition Threshold */}
            <div className="setting-row">
              <div className="setting-label">
                <span>Recognition Threshold</span>
                <span className="setting-hint">Similarity score to match a face (lower = stricter matching)</span>
              </div>
              <div className="setting-control">
                <input
                  type="range"
                  min={settings.ranges.recognition_threshold.min}
                  max={settings.ranges.recognition_threshold.max}
                  step={settings.ranges.recognition_threshold.step}
                  value={getCurrentValue('recognition_threshold') || settings.recognition_threshold}
                  onChange={(e) => handleSettingChange('recognition_threshold', parseFloat(e.target.value))}
                />
                <span className="setting-value">
                  {(getCurrentValue('recognition_threshold') || settings.recognition_threshold).toFixed(2)}
                </span>
              </div>
            </div>

            {/* Frame Skip */}
            <div className="setting-row">
              <div className="setting-label">
                <span>Frame Skip</span>
                <span className="setting-hint">Process every Nth frame (higher = less CPU, lower FPS)</span>
              </div>
              <div className="setting-control">
                <input
                  type="range"
                  min={settings.ranges.frame_skip.min}
                  max={settings.ranges.frame_skip.max}
                  step={settings.ranges.frame_skip.step}
                  value={getCurrentValue('frame_skip') || settings.frame_skip}
                  onChange={(e) => handleSettingChange('frame_skip', parseInt(e.target.value))}
                />
                <span className="setting-value">
                  {getCurrentValue('frame_skip') || settings.frame_skip}
                </span>
              </div>
            </div>

            {/* Motion Trigger */}
            <div className="setting-row">
              <div className="setting-label">
                <span>Motion Trigger</span>
                <span className="setting-hint">Only detect faces when camera sees motion</span>
              </div>
              <div className="setting-control">
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={getCurrentValue('enable_motion_trigger') ?? settings.enable_motion_trigger}
                    onChange={(e) => handleSettingChange('enable_motion_trigger', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
                <span className="setting-value">
                  {(getCurrentValue('enable_motion_trigger') ?? settings.enable_motion_trigger) ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </div>

            {/* Alert Cooldown */}
            <div className="setting-row">
              <div className="setting-label">
                <span>Alert Cooldown</span>
                <span className="setting-hint">Seconds between alerts for the same person (1-300)</span>
              </div>
              <div className="setting-control">
                <input
                  type="range"
                  min={settings.ranges.alert_cooldown_seconds?.min || 1}
                  max={settings.ranges.alert_cooldown_seconds?.max || 300}
                  step={settings.ranges.alert_cooldown_seconds?.step || 1}
                  value={getCurrentValue('alert_cooldown_seconds') || settings.alert_cooldown_seconds}
                  onChange={(e) => handleSettingChange('alert_cooldown_seconds', parseInt(e.target.value))}
                />
                <span className="setting-value">
                  {getCurrentValue('alert_cooldown_seconds') || settings.alert_cooldown_seconds}s
                </span>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      {/* Video Recording Settings */}
      <section className="settings-section">
        <h3>
          <Video size={20} />
          Video Recording
        </h3>

        {settings && (
          <div className="settings-form">
            {/* Video Recording Toggle */}
            <div className="setting-row">
              <div className="setting-label">
                <span>Record Video Clips</span>
                <span className="setting-hint">Save video footage around each alert</span>
              </div>
              <div className="setting-control">
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={getCurrentValue('video_recording_enabled') ?? settings.video_recording_enabled}
                    onChange={(e) => handleSettingChange('video_recording_enabled', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
                <span className="setting-value">
                  {(getCurrentValue('video_recording_enabled') ?? settings.video_recording_enabled) ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </div>

            {/* Video Clip Duration */}
            {(getCurrentValue('video_recording_enabled') ?? settings.video_recording_enabled) && (
              <div className="setting-row">
                <div className="setting-label">
                  <span>Clip Duration</span>
                  <span className="setting-hint">Seconds before and after alert to record (3-10)</span>
                </div>
                <div className="setting-control">
                  <input
                    type="range"
                    min={settings.ranges.video_clip_duration?.min || 3}
                    max={settings.ranges.video_clip_duration?.max || 10}
                    step={settings.ranges.video_clip_duration?.step || 1}
                    value={getCurrentValue('video_clip_duration') || settings.video_clip_duration}
                    onChange={(e) => handleSettingChange('video_clip_duration', parseInt(e.target.value))}
                  />
                  <span className="setting-value">
                    {getCurrentValue('video_clip_duration') || settings.video_clip_duration}s before + after
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Storage Management */}
      <section className="settings-section">
        <h3>
          <Database size={20} />
          Storage Management
          <button className="refresh-btn" onClick={loadStorage} title="Refresh">
            <RefreshCw size={16} />
          </button>
        </h3>

        {storage && (
          <div className="storage-section">
            {/* Storage Warning */}
            {storage.warning && (
              <div className="storage-warning">
                <AlertTriangle size={20} />
                <div>
                  <strong>Storage Warning!</strong>
                  <p>{storage.message}</p>
                </div>
              </div>
            )}

            {/* Disk Usage */}
            <div className="storage-stats">
              <div className="storage-stat">
                <div className="storage-stat-header">
                  <HardDrive size={18} />
                  <span>Disk Usage</span>
                </div>
                <div className="storage-bar">
                  <div
                    className={`storage-bar-fill ${storage.disk.percent_used >= 70 ? 'warning' : ''} ${storage.disk.percent_used >= 90 ? 'critical' : ''}`}
                    style={{ width: `${storage.disk.percent_used}%` }}
                  />
                </div>
                <div className="storage-stat-details">
                  <span>{storage.disk.used_gb} GB / {storage.disk.total_gb} GB</span>
                  <span className={storage.disk.percent_used >= 70 ? 'text-warning' : ''}>{storage.disk.percent_used}%</span>
                </div>
              </div>

              <div className="storage-stat">
                <div className="storage-stat-header">
                  <Video size={18} />
                  <span>Alert Data</span>
                </div>
                <div className="storage-stat-details alerts-data">
                  <span>{storage.alerts_data.snapshots} snapshots</span>
                  <span>{storage.alerts_data.videos} videos</span>
                  <span>{storage.alerts_data.size_mb > 1000 ? `${storage.alerts_data.size_gb} GB` : `${storage.alerts_data.size_mb} MB`}</span>
                </div>
              </div>
            </div>

            {/* Cleanup Controls */}
            <div className="cleanup-controls">
              <div className="cleanup-input">
                <label>Delete data older than:</label>
                <select value={cleanupDays} onChange={(e) => setCleanupDays(parseInt(e.target.value))}>
                  <option value={7}>7 days</option>
                  <option value={14}>14 days</option>
                  <option value={30}>30 days</option>
                  <option value={60}>60 days</option>
                  <option value={90}>90 days</option>
                </select>
              </div>
              <button
                className="btn btn-danger"
                onClick={handleCleanup}
                disabled={cleaningUp}
              >
                <Trash2 size={16} />
                {cleaningUp ? 'Cleaning...' : 'Cleanup Old Data'}
              </button>
            </div>

            {storageMessage && (
              <div className={`save-message ${storageMessage.type}`}>
                {storageMessage.text}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Model Selection */}
      <section className="settings-section">
        <h3>
          <Settings size={20} />
          Model Selection
        </h3>

        {models && (
          <>
            <div className="model-selection">
              {models.packs.map((pack) => (
                <div
                  key={pack.id}
                  className={`model-card selectable ${models.current.model === pack.id ? 'selected' : ''} ${!pack.available ? 'disabled' : ''}`}
                  onClick={() => pack.available && !changingModel && handleModelChange(pack.id)}
                >
                  <div className="model-header">
                    <h4>{pack.name}</h4>
                    {models.current.model === pack.id && (
                      <span className="current-badge">Current</span>
                    )}
                  </div>
                  <p className="model-description">{pack.description}</p>
                  <div className="model-details">
                    <span>Size: {pack.size_mb}MB (FP16)</span>
                    <span>FPS: {pack.fps_estimate}</span>
                    <span>Accuracy: {pack.accuracy}</span>
                  </div>
                  <div className="model-components">
                    <small>Detection: {pack.detection}</small>
                    <small>Recognition: {pack.recognition}</small>
                  </div>
                  {!pack.available && (
                    <div className="model-unavailable">Not downloaded</div>
                  )}
                </div>
              ))}
            </div>

            {changingModel && (
              <div className="model-changing">
                <RefreshCw size={16} className="spinning" />
                Switching model... Stream will restart automatically.
              </div>
            )}

            {modelMessage && (
              <div className={`save-message ${modelMessage.type}`}>
                {modelMessage.text}
              </div>
            )}

            <div className="model-info">
              <p>
                <strong>Current:</strong> {models.current.full_name}
                {models.current.using_fp16 && <span className="fp16-badge">FP16</span>}
              </p>
            </div>
          </>
        )}
      </section>

      {/* Save/Reset Buttons */}
      {hasChanges && (
        <div className="settings-actions">
          <button className="btn btn-secondary" onClick={discardChanges}>
            <RotateCcw size={16} />
            Discard
          </button>
          <button className="btn btn-secondary" onClick={resetToDefaults}>
            <RotateCcw size={16} />
            Reset to Defaults
          </button>
          <button className="btn btn-primary" onClick={saveSettings} disabled={saving}>
            <Save size={16} />
            {saving ? 'Applying...' : 'Apply Settings'}
          </button>
        </div>
      )}

      {/* Save Message */}
      {saveMessage && (
        <div className={`save-message ${saveMessage.type}`}>
          {saveMessage.text}
        </div>
      )}
    </div>
  );
}

export default SystemSettings;
