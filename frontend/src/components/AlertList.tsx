import { useEffect, useState, useCallback } from 'react';
import { alertsApi } from '../services/api';
import { Bell, Check, Trash2, AlertCircle, User } from 'lucide-react';

interface Alert {
  id: number;
  timestamp: string;
  person_id: number | null;
  person_name: string | null;
  alert_type: string;
  confidence: number;
  acknowledged: boolean;
  snapshot_path: string | null;
}

export function AlertList() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [ws, setWs] = useState<WebSocket | null>(null);

  const loadAlerts = useCallback(async () => {
    try {
      setLoading(true);
      const response = await alertsApi.list({ limit: 50 });
      setAlerts(response.data);
    } catch (err) {
      console.error('Failed to load alerts:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAlerts();

    // Connect to WebSocket for real-time alerts
    const websocket = new WebSocket(alertsApi.getWebSocketUrl());

    websocket.onmessage = (event) => {
      const newAlert = JSON.parse(event.data);
      setAlerts((prev) => [newAlert, ...prev]);

      // Show browser notification
      if (Notification.permission === 'granted') {
        new Notification('Face Recognition Alert', {
          body: `${newAlert.alert_type}: ${newAlert.person_name || 'Unknown'}`,
        });
      }
    };

    websocket.onerror = () => {
      console.log('WebSocket connection failed');
    };

    setWs(websocket);

    // Request notification permission
    if (Notification.permission === 'default') {
      Notification.requestPermission();
    }

    return () => {
      websocket.close();
    };
  }, [loadAlerts]);

  const handleAcknowledge = async (alertId: number) => {
    try {
      await alertsApi.acknowledge(alertId);
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, acknowledged: true } : a))
      );
    } catch (err) {
      console.error('Acknowledge failed:', err);
    }
  };

  const handleDelete = async (alertId: number) => {
    try {
      await alertsApi.delete(alertId);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div className="alert-list">
      <div className="alert-header">
        <h3>
          <Bell size={20} /> Alerts
        </h3>
        <span className="alert-count">{alerts.filter((a) => !a.acknowledged).length} unread</span>
      </div>

      {loading ? (
        <div className="loading">Loading alerts...</div>
      ) : alerts.length === 0 ? (
        <div className="empty">No alerts yet</div>
      ) : (
        <ul className="alerts">
          {alerts.map((alert) => (
            <li
              key={alert.id}
              className={`alert-item ${alert.acknowledged ? 'acknowledged' : 'unread'} ${alert.alert_type}`}
            >
              <div className="alert-icon">
                {alert.alert_type === 'known' ? (
                  <User size={24} className="icon-known" />
                ) : (
                  <AlertCircle size={24} className="icon-unknown" />
                )}
              </div>

              <div className="alert-content">
                <div className="alert-title">
                  {alert.alert_type === 'known'
                    ? `Recognized: ${alert.person_name}`
                    : 'Unknown Person Detected'}
                </div>
                <div className="alert-meta">
                  <span className="alert-time">{formatTime(alert.timestamp)}</span>
                  <span className="alert-confidence">
                    Confidence: {(alert.confidence * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              <div className="alert-actions">
                {!alert.acknowledged && (
                  <button
                    onClick={() => handleAcknowledge(alert.id)}
                    className="ack-btn"
                    title="Acknowledge"
                  >
                    <Check size={16} />
                  </button>
                )}
                <button
                  onClick={() => handleDelete(alert.id)}
                  className="delete-btn"
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default AlertList;
