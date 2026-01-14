import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://192.168.0.245:8000/api';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Stream API
export const streamApi = {
  start: () => api.get('/stream/start'),
  stop: () => api.get('/stream/stop'),
  status: () => api.get('/stream/status'),
  getBaseUrl: () => API_BASE_URL,
  // Full tiled view (all cameras combined)
  getMjpegUrl: () => `${API_BASE_URL}/stream/mjpeg`,
  getWebSocketUrl: () => `ws://${API_BASE_URL.replace('http://', '')}/stream/ws`,
  // Single camera stream (cropped from tiled view, WITH overlays)
  getCameraMjpegUrl: (cameraId: number) => `${API_BASE_URL}/stream/mjpeg/camera/${cameraId}`,
  // Raw stream (no overlays/bounding boxes) for enrollment
  getRawMjpegUrl: () => `${API_BASE_URL}/stream/mjpeg/raw`,
  getRawWebSocketUrl: () => `ws://${API_BASE_URL.replace('http://', '')}/stream/ws/raw`,
  // Single camera RAW stream (no overlays) - for enrollment preview
  getCameraRawMjpegUrl: (cameraId: number) => `${API_BASE_URL}/stream/mjpeg/camera/${cameraId}/raw`,
  // Snapshot endpoints
  getSnapshotUrl: () => `${API_BASE_URL}/stream/snapshot`,
  getCameraSnapshotUrl: (cameraId: number) => `${API_BASE_URL}/stream/snapshot/camera/${cameraId}`,
  // Camera switching
  getCurrentCamera: () => api.get('/stream/camera'),
  switchCamera: (cameraId: number) => api.post(`/stream/camera/${cameraId}`),
};

// Persons API
export const personsApi = {
  list: (search?: string) => api.get('/persons/', { params: search ? { search } : undefined }),
  getDetails: (personId: number) => api.get(`/persons/${personId}/details`),
  enroll: (name: string, image: File, idCard?: string, caseInfo?: string, watchlistStatus?: string, threatLevel?: string) => {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('image', image);
    if (idCard) formData.append('id_card', idCard);
    if (caseInfo) formData.append('case', caseInfo);
    if (watchlistStatus) formData.append('watchlist_status', watchlistStatus);
    if (threatLevel) formData.append('threat_level', threatLevel);
    return api.post('/persons/enroll', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  enrollFromCamera: (name: string, idCard?: string, caseInfo?: string, watchlistStatus?: string, threatLevel?: string, cameraId?: number) => {
    const params = new URLSearchParams({ name });
    if (idCard) params.append('id_card', idCard);
    if (caseInfo) params.append('case', caseInfo);
    if (watchlistStatus) params.append('watchlist_status', watchlistStatus);
    if (threatLevel) params.append('threat_level', threatLevel);
    if (cameraId !== undefined) params.append('camera_id', cameraId.toString());
    return api.post(`/persons/enroll-from-camera?${params.toString()}`);
  },
  addImage: (personId: number, image: File) => {
    const formData = new FormData();
    formData.append('image', image);
    return api.post(`/persons/${personId}/add-image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  delete: (personId: number) => api.delete(`/persons/${personId}`),
  stats: () => api.get('/persons/stats'),
};

// Alerts API
export const alertsApi = {
  list: (params?: {
    limit?: number;
    offset?: number;
    acknowledged?: boolean;
    search?: string;
    time_range?: string;  // "24h", "7d", "30d", "all"
    threat_level?: string;
    person_id?: number;
  }) => api.get('/alerts/', { params }),
  acknowledge: (alertId: number) => api.post(`/alerts/${alertId}/acknowledge`),
  verify: (alertId: number, action: string, notes?: string) =>
    api.post(`/alerts/${alertId}/verify`, null, { params: { action, notes } }),
  delete: (alertId: number) => api.delete(`/alerts/${alertId}`),
  getWebSocketUrl: () => `ws://${API_BASE_URL.replace('http://', '')}/alerts/ws`,
  getSnapshotUrl: (alertId: number, timestamp?: number) =>
    `${API_BASE_URL}/alerts/${alertId}/snapshot?t=${timestamp || Date.now()}`,
  getVideoUrl: (alertId: number) =>
    `${API_BASE_URL}/alerts/${alertId}/video`,
  checkVideoExists: (alertId: number) =>
    api.get(`/alerts/${alertId}/video/exists`),
  exportCsv: (params?: { time_range?: string; search?: string; threat_level?: string }) => {
    const queryString = new URLSearchParams(
      Object.entries(params || {}).filter(([_, v]) => v !== undefined) as [string, string][]
    ).toString();
    return `${API_BASE_URL}/alerts/export/csv${queryString ? '?' + queryString : ''}`;
  },
};

// Get person reference image URL with cache-busting timestamp
export const getPersonImageUrl = (personId: number, timestamp?: number) =>
  `${API_BASE_URL}/persons/${personId}/image?t=${timestamp || Date.now()}`;

// Cameras API
export const camerasApi = {
  list: (enabledOnly: boolean = false) =>
    api.get('/cameras/', { params: enabledOnly ? { enabled_only: true } : undefined }),
  get: (cameraId: number) => api.get(`/cameras/${cameraId}`),
  create: (data: {
    name: string;
    ip_address: string;
    port?: number;
    username: string;
    password: string;
    stream_quality?: string;
    enabled?: boolean;
    detection_enabled?: boolean;
    detection_confidence?: number;
    recognition_threshold?: number;
    frame_skip?: number;
    location?: string;
    notes?: string;
  }) => api.post('/cameras/', data),
  update: (cameraId: number, data: {
    name?: string;
    ip_address?: string;
    port?: number;
    username?: string;
    password?: string;
    stream_quality?: string;
    enabled?: boolean;
    detection_enabled?: boolean;
    detection_confidence?: number;
    recognition_threshold?: number;
    frame_skip?: number;
    location?: string;
    notes?: string;
  }) => api.put(`/cameras/${cameraId}`, data),
  delete: (cameraId: number) => api.delete(`/cameras/${cameraId}`),
  test: (cameraId: number) => api.post(`/cameras/${cameraId}/test`),
  snapshot: (cameraId: number) => `${API_BASE_URL}/cameras/${cameraId}/snapshot?t=${Date.now()}`,
  enable: (cameraId: number) => api.post(`/cameras/${cameraId}/enable`),
  disable: (cameraId: number) => api.post(`/cameras/${cameraId}/disable`),
  getQualityOptions: () => api.get('/cameras/quality-options'),
  getSummary: () => api.get('/cameras/stats/summary'),
};

// System API
export const systemApi = {
  status: () => api.get('/system/status'),
  cameraInfo: () => api.get('/system/camera/info'),
  // Resource monitoring
  resources: () => api.get('/system/resources'),
  // Storage monitoring
  storage: () => api.get('/system/storage'),
  cleanupStorage: (days: number = 30) => api.post('/system/storage/cleanup', null, { params: { days } }),
  // Settings
  getSettings: () => api.get('/system/settings'),
  updateSettings: (settings: {
    detection_confidence?: number;
    recognition_threshold?: number;
    frame_skip?: number;
    enable_motion_trigger?: boolean;
    alert_cooldown_seconds?: number;
    video_recording_enabled?: boolean;
    video_clip_duration?: number;
  }) => api.post('/system/settings/update', null, { params: settings }),
  // Available models
  getModels: () => api.get('/system/models'),
  changeModel: (model: string, useFp16: boolean = true) =>
    api.post('/system/models/change', null, { params: { model, use_fp16: useFp16 } }),
  // Camera PTZ zoom control (optional camera_id for multi-camera support)
  zoomIn: (speed: number = 50, cameraId?: number) =>
    api.post('/system/camera/zoom', null, { params: { action: 'in', speed, camera_id: cameraId } }),
  zoomOut: (speed: number = 50, cameraId?: number) =>
    api.post('/system/camera/zoom', null, { params: { action: 'out', speed, camera_id: cameraId } }),
  zoomStop: (cameraId?: number) =>
    api.post('/system/camera/zoom', null, { params: { action: 'stop', camera_id: cameraId } }),
  zoomSet: (level: number, cameraId?: number) =>
    api.post('/system/camera/zoom/set', null, { params: { level, camera_id: cameraId } }),
  ptzStatus: (cameraId?: number) =>
    api.get('/system/camera/ptz/status', { params: cameraId ? { camera_id: cameraId } : undefined }),
};

export default api;
