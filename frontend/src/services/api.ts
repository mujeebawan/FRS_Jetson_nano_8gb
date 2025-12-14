import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { getAccessToken } from '@/contexts/AuthContext';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://192.168.0.245:8000/api';

export const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
axiosInstance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle 401 errors
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - redirect to login
      // Clear stored tokens
      localStorage.removeItem('frs_access_token');
      localStorage.removeItem('frs_refresh_token');
      localStorage.removeItem('frs_user');

      // Redirect to login (only if not already on login page)
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Helper to get token for URL params (for streams/websockets)
export const getTokenParam = (): string => {
  const token = getAccessToken();
  return token ? `token=${encodeURIComponent(token)}` : '';
};

// Stream API
export const streamApi = {
  start: () => axiosInstance.get('/stream/start').then(res => res.data),
  stop: () => axiosInstance.get('/stream/stop').then(res => res.data),
  status: () => axiosInstance.get('/stream/status').then(res => res.data),
  getBaseUrl: () => API_BASE_URL,
  getMjpegUrl: () => {
    const token = getAccessToken();
    return `${API_BASE_URL}/stream/mjpeg?token=${encodeURIComponent(token || '')}`;
  },
  getWebSocketUrl: () => {
    const token = getAccessToken();
    const wsBase = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
    return `${wsBase}/stream/ws?token=${encodeURIComponent(token || '')}`;
  },
  getRawMjpegUrl: () => {
    const token = getAccessToken();
    return `${API_BASE_URL}/stream/mjpeg/raw?token=${encodeURIComponent(token || '')}`;
  },
  getRawWebSocketUrl: () => {
    const token = getAccessToken();
    const wsBase = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
    return `${wsBase}/stream/ws/raw?token=${encodeURIComponent(token || '')}`;
  },
};

// Persons API
export const personsApi = {
  list: (search?: string) =>
    axiosInstance.get('/persons/', { params: search ? { search } : undefined }).then(res => res.data),
  getDetails: (personId: number) =>
    axiosInstance.get(`/persons/${personId}/details`).then(res => res.data),
  enroll: (name: string, image: File, idCard?: string, caseInfo?: string, watchlistStatus?: string, threatLevel?: string) => {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('image', image);
    if (idCard) formData.append('id_card', idCard);
    if (caseInfo) formData.append('case', caseInfo);
    if (watchlistStatus) formData.append('watchlist_status', watchlistStatus);
    if (threatLevel) formData.append('threat_level', threatLevel);
    return axiosInstance.post('/persons/enroll', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(res => res.data);
  },
  enrollFromCamera: (name: string, idCard?: string, caseInfo?: string, watchlistStatus?: string, threatLevel?: string) => {
    const params = new URLSearchParams({ name });
    if (idCard) params.append('id_card', idCard);
    if (caseInfo) params.append('case', caseInfo);
    if (watchlistStatus) params.append('watchlist_status', watchlistStatus);
    if (threatLevel) params.append('threat_level', threatLevel);
    return axiosInstance.post(`/persons/enroll-from-camera?${params.toString()}`).then(res => res.data);
  },
  addImage: (personId: number, image: File) => {
    const formData = new FormData();
    formData.append('image', image);
    return axiosInstance.post(`/persons/${personId}/add-image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(res => res.data);
  },
  delete: (personId: number) => axiosInstance.delete(`/persons/${personId}`).then(res => res.data),
  stats: () => axiosInstance.get('/persons/stats').then(res => res.data),
  getImageUrl: (personId: number, timestamp?: number) => {
    const token = getAccessToken();
    return `${API_BASE_URL}/persons/${personId}/image?t=${timestamp || Date.now()}&token=${encodeURIComponent(token || '')}`;
  },
};

// Alerts API
export const alertsApi = {
  list: (params?: {
    limit?: number;
    offset?: number;
    acknowledged?: boolean;
    search?: string;
    time_range?: string;
    threat_level?: string;
    person_id?: number;
  }) => axiosInstance.get('/alerts/', { params }).then(res => res.data),
  acknowledge: (alertId: number) =>
    axiosInstance.post(`/alerts/${alertId}/acknowledge`).then(res => res.data),
  verify: (alertId: number, action: string, notes?: string) =>
    axiosInstance.post(`/alerts/${alertId}/verify`, null, { params: { action, notes } }).then(res => res.data),
  delete: (alertId: number) => axiosInstance.delete(`/alerts/${alertId}`).then(res => res.data),
  getWebSocketUrl: () => {
    const token = getAccessToken();
    const wsBase = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
    return `${wsBase}/alerts/ws?token=${encodeURIComponent(token || '')}`;
  },
  getSnapshotUrl: (alertId: number, timestamp?: number) => {
    const token = getAccessToken();
    return `${API_BASE_URL}/alerts/${alertId}/snapshot?t=${timestamp || Date.now()}&token=${encodeURIComponent(token || '')}`;
  },
  getVideoUrl: (alertId: number) => {
    const token = getAccessToken();
    return `${API_BASE_URL}/alerts/${alertId}/video?token=${encodeURIComponent(token || '')}`;
  },
  checkVideoExists: (alertId: number) =>
    axiosInstance.get(`/alerts/${alertId}/video/exists`).then(res => res.data),
  exportCsv: (params?: { time_range?: string; search?: string; threat_level?: string }) => {
    const token = getAccessToken();
    const queryParams = new URLSearchParams(
      Object.entries(params || {}).filter(([, v]) => v !== undefined) as [string, string][]
    );
    queryParams.append('token', token || '');
    return `${API_BASE_URL}/alerts/export/csv?${queryParams.toString()}`;
  },
};

// System API
export const systemApi = {
  status: () => axiosInstance.get('/system/status').then(res => res.data),
  cameraInfo: () => axiosInstance.get('/system/camera/info').then(res => res.data),
  resources: () => axiosInstance.get('/system/resources').then(res => res.data),
  storage: () => axiosInstance.get('/system/storage').then(res => res.data),
  cleanupStorage: (days: number = 30) =>
    axiosInstance.post('/system/storage/cleanup', null, { params: { days } }).then(res => res.data),
  getSettings: () => axiosInstance.get('/system/settings').then(res => res.data),
  updateSettings: (settings: {
    detection_confidence?: number;
    recognition_threshold?: number;
    frame_skip?: number;
    enable_motion_trigger?: boolean;
    alert_cooldown_seconds?: number;
    video_recording_enabled?: boolean;
    video_clip_duration?: number;
  }) => axiosInstance.post('/system/settings/update', null, { params: settings }).then(res => res.data),
  getModels: () => axiosInstance.get('/system/models').then(res => res.data),
  changeModel: (model: string, useFp16: boolean = true) =>
    axiosInstance.post('/system/models/change', null, { params: { model, use_fp16: useFp16 } }).then(res => res.data),
  zoomIn: (speed: number = 50) =>
    axiosInstance.post('/system/camera/zoom', null, { params: { action: 'in', speed } }).then(res => res.data),
  zoomOut: (speed: number = 50) =>
    axiosInstance.post('/system/camera/zoom', null, { params: { action: 'out', speed } }).then(res => res.data),
  zoomStop: () =>
    axiosInstance.post('/system/camera/zoom', null, { params: { action: 'stop' } }).then(res => res.data),
  zoomSet: (level: number) =>
    axiosInstance.post('/system/camera/zoom/set', null, { params: { level } }).then(res => res.data),
  ptzStatus: () => axiosInstance.get('/system/camera/ptz/status').then(res => res.data),
};

// Users API (admin only)
export const usersApi = {
  list: (skip?: number, limit?: number) =>
    axiosInstance.get('/users', { params: { skip, limit } }).then(res => res.data),
  create: (user: { username: string; password: string; email?: string; role: string }) =>
    axiosInstance.post('/users', user).then(res => res.data),
  get: (userId: number) =>
    axiosInstance.get(`/users/${userId}`).then(res => res.data),
  update: (userId: number, data: { email?: string; role?: string; is_active?: boolean }) =>
    axiosInstance.put(`/users/${userId}`, data).then(res => res.data),
  delete: (userId: number) =>
    axiosInstance.delete(`/users/${userId}`).then(res => res.data),
  resetPassword: (userId: number, newPassword: string) =>
    axiosInstance.post(`/users/${userId}/reset-password`, { new_password: newPassword }).then(res => res.data),
};

// Auth API
export const authApi = {
  login: (username: string, password: string) =>
    axiosInstance.post('/auth/login', { username, password }).then(res => res.data),
  refresh: (refreshToken: string) =>
    axiosInstance.post('/auth/refresh', { refresh_token: refreshToken }).then(res => res.data),
  logout: () =>
    axiosInstance.post('/auth/logout').then(res => res.data),
  me: () =>
    axiosInstance.get('/auth/me').then(res => res.data),
  changePassword: (currentPassword: string, newPassword: string) =>
    axiosInstance.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }).then(res => res.data),
};

// Unified API export
const api = {
  stream: streamApi,
  persons: personsApi,
  alerts: alertsApi,
  system: systemApi,
  users: usersApi,
  auth: authApi,
};

export default api;
