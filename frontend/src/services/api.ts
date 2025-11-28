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
  getMjpegUrl: () => `${API_BASE_URL}/stream/mjpeg`,
  getWebSocketUrl: () => `ws://${API_BASE_URL.replace('http://', '')}/stream/ws`,
};

// Persons API
export const personsApi = {
  list: () => api.get('/persons'),
  enroll: (name: string, image: File) => {
    const formData = new FormData();
    formData.append('image', image);
    return api.post(`/persons/enroll?name=${encodeURIComponent(name)}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
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
  list: (params?: { limit?: number; offset?: number; acknowledged?: boolean }) =>
    api.get('/alerts', { params }),
  acknowledge: (alertId: number) => api.post(`/alerts/${alertId}/acknowledge`),
  delete: (alertId: number) => api.delete(`/alerts/${alertId}`),
  getWebSocketUrl: () => `ws://${API_BASE_URL.replace('http://', '')}/alerts/ws`,
};

// System API
export const systemApi = {
  status: () => api.get('/system/status'),
  cameraInfo: () => api.get('/system/camera/info'),
  updateSettings: (settings: {
    detection_confidence?: number;
    recognition_threshold?: number;
    frame_skip?: number;
  }) => api.post('/system/settings/update', null, { params: settings }),
};

export default api;
