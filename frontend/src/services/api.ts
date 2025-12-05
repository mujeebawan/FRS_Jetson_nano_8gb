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
  getMjpegUrl: () => `${API_BASE_URL}/stream/mjpeg`,
  getWebSocketUrl: () => `ws://${API_BASE_URL.replace('http://', '')}/stream/ws`,
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
  enrollFromCamera: (name: string, idCard?: string, caseInfo?: string, watchlistStatus?: string, threatLevel?: string) => {
    const params = new URLSearchParams({ name });
    if (idCard) params.append('id_card', idCard);
    if (caseInfo) params.append('case', caseInfo);
    if (watchlistStatus) params.append('watchlist_status', watchlistStatus);
    if (threatLevel) params.append('threat_level', threatLevel);
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

// System API
export const systemApi = {
  status: () => api.get('/system/status'),
  cameraInfo: () => api.get('/system/camera/info'),
  // Resource monitoring
  resources: () => api.get('/system/resources'),
  // Settings
  getSettings: () => api.get('/system/settings'),
  updateSettings: (settings: {
    detection_confidence?: number;
    recognition_threshold?: number;
    frame_skip?: number;
    enable_motion_trigger?: boolean;
    alert_cooldown_seconds?: number;
  }) => api.post('/system/settings/update', null, { params: settings }),
  // Available models
  getModels: () => api.get('/system/models'),
  changeModel: (model: string, useFp16: boolean = true) =>
    api.post('/system/models/change', null, { params: { model, use_fp16: useFp16 } }),
  // Camera PTZ zoom control
  zoomIn: (speed: number = 50) => api.post('/system/camera/zoom', null, { params: { action: 'in', speed } }),
  zoomOut: (speed: number = 50) => api.post('/system/camera/zoom', null, { params: { action: 'out', speed } }),
  zoomStop: () => api.post('/system/camera/zoom', null, { params: { action: 'stop' } }),
  zoomSet: (level: number) => api.post('/system/camera/zoom/set', null, { params: { level } }),
  ptzStatus: () => api.get('/system/camera/ptz/status'),
};

export default api;
