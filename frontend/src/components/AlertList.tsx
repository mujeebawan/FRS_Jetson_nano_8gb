import React, { useEffect, useState, useCallback } from 'react';
import { alertsApi, getPersonImageUrl } from '../services/api';
import {
  Bell, Check, Trash2, AlertCircle, User, Shield, AlertTriangle,
  CheckCircle, XCircle, Phone, Volume2, DoorClosed, X, Siren,
  Search, Download, Calendar, Filter, RefreshCw
} from 'lucide-react';

interface Alert {
  id: number;
  timestamp: string;
  person_id: number | null;
  person_name: string | null;
  alert_type: string;
  confidence: number;
  acknowledged: boolean;
  snapshot_path: string | null;
  // Extended fields
  similarity_score?: number;
  threat_level?: string;
  watchlist_status?: string;
  displayed_prompt?: string;
  guard_verified?: boolean;
  guard_action?: string;
}

interface FilterState {
  search: string;
  timeRange: string;
  threatLevel: string;
  acknowledged?: boolean;
}

interface AlertListProps {
  /** Show full page with filters, search, and export. False = compact dashboard view */
  fullPage?: boolean;
}

export function AlertList({ fullPage = false }: AlertListProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalAlert, setModalAlert] = useState<Alert | null>(null);
  const [verifying, setVerifying] = useState<number | null>(null);

  // Alert queue for handling multiple detections one by one
  const [alertQueue, setAlertQueue] = useState<Alert[]>([]);
  const alertQueueRef = React.useRef<Alert[]>([]);

  // Filter state
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    timeRange: 'all',
    threatLevel: '',
  });
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(filters.search);
    }, 300);
    return () => clearTimeout(timer);
  }, [filters.search]);

  const loadAlerts = useCallback(async () => {
    try {
      setLoading(true);
      // Dashboard view: always 24h, no filters. Full page: use filter state
      const params = fullPage
        ? {
            limit: 100,
            search: debouncedSearch || undefined,
            time_range: filters.timeRange !== 'all' ? filters.timeRange : undefined,
            threat_level: filters.threatLevel || undefined,
          }
        : {
            limit: 50,
            time_range: '24h',
          };
      const response = await alertsApi.list(params);
      setAlerts(response.data);
    } catch (err) {
      console.error('Failed to load alerts:', err);
    } finally {
      setLoading(false);
    }
  }, [fullPage, debouncedSearch, filters.timeRange, filters.threatLevel]);

  // Reload when filters change
  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  const handleExportCsv = () => {
    const url = alertsApi.exportCsv({
      time_range: filters.timeRange !== 'all' ? filters.timeRange : undefined,
      search: debouncedSearch || undefined,
      threat_level: filters.threatLevel || undefined,
    });
    window.open(url, '_blank');
  };

  // Track last seen alert ID for polling
  const lastAlertIdRef = React.useRef<number>(0);
  const wsConnectedRef = React.useRef<boolean>(false);

  // WebSocket for real-time alerts with reconnection
  useEffect(() => {
    let websocket: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
    let isUnmounting = false;

    const connect = () => {
      if (isUnmounting) return;

      const wsUrl = alertsApi.getWebSocketUrl();
      console.log('Connecting to WebSocket:', wsUrl);
      websocket = new WebSocket(wsUrl);

      websocket.onopen = () => {
        console.log('WebSocket connected successfully');
        wsConnectedRef.current = true;
      };

      websocket.onmessage = (event) => {
        console.log('WebSocket received:', event.data);
        const newAlert = JSON.parse(event.data);

        // Update last seen ID
        if (newAlert.id > lastAlertIdRef.current) {
          lastAlertIdRef.current = newAlert.id;
        }

        setAlerts((prev) => {
          // Avoid duplicates
          if (prev.some(a => a.id === newAlert.id)) return prev;
          return [newAlert, ...prev];
        });

        // Queue system: Add to queue instead of immediately showing
        // If no modal is open, show immediately. Otherwise, add to queue.
        setAlertQueue((prevQueue) => {
          const updatedQueue = [...prevQueue, newAlert];
          alertQueueRef.current = updatedQueue;
          return updatedQueue;
        });

        // Show browser notification
        if (Notification.permission === 'granted') {
          const title = newAlert.threat_level === 'critical' ? 'CRITICAL ALERT!' : 'Face Recognition Alert';
          new Notification(title, {
            body: `${newAlert.watchlist_status?.toUpperCase() || newAlert.alert_type}: ${newAlert.person_name || 'Unknown'}\n${newAlert.displayed_prompt || ''}`,
            requireInteraction: newAlert.threat_level === 'critical',
          });
        }
      };

      websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        wsConnectedRef.current = false;
      };

      websocket.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        wsConnectedRef.current = false;
        // Reconnect after 3 seconds
        if (!isUnmounting) {
          reconnectTimeout = setTimeout(connect, 3000);
        }
      };
    };

    connect();

    // Request notification permission
    if (Notification.permission === 'default') {
      Notification.requestPermission();
    }

    return () => {
      isUnmounting = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (websocket) websocket.close();
    };
  }, []);

  // Polling fallback - refresh every 5 seconds if WebSocket is not connected
  useEffect(() => {
    const pollInterval = setInterval(() => {
      if (!wsConnectedRef.current) {
        console.log('WebSocket not connected, polling for alerts...');
        loadAlerts();
      }
    }, 5000);

    return () => clearInterval(pollInterval);
  }, [loadAlerts]);

  // Also auto-refresh every 30 seconds regardless (for staleness)
  useEffect(() => {
    const refreshInterval = setInterval(() => {
      loadAlerts();
    }, 30000);

    return () => clearInterval(refreshInterval);
  }, [loadAlerts]);

  // Process alert queue - show next alert when modal is closed
  useEffect(() => {
    // If no modal is open and there are alerts in queue, show the first one
    if (!modalAlert && alertQueue.length > 0) {
      const nextAlert = alertQueue[0];
      setModalAlert(nextAlert);
      // Remove from queue
      setAlertQueue((prev) => {
        const newQueue = prev.slice(1);
        alertQueueRef.current = newQueue;
        return newQueue;
      });
    }
  }, [modalAlert, alertQueue]);

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

  const handleVerify = async (alertId: number, action: string) => {
    try {
      setVerifying(alertId);
      await alertsApi.verify(alertId, action);
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, guard_verified: true, guard_action: action, acknowledged: true } : a))
      );
      // Update modal alert if it's the same
      if (modalAlert && modalAlert.id === alertId) {
        setModalAlert({ ...modalAlert, guard_verified: true, guard_action: action, acknowledged: true });
      }
    } catch (err) {
      console.error('Verify failed:', err);
    } finally {
      setVerifying(null);
    }
  };

  const openAlertModal = (alert: Alert) => {
    setModalAlert(alert);
  };

  const closeModal = () => {
    setModalAlert(null);
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
    <>
      {/* Alert Modal Popup */}
      {modalAlert && (
        <div className="alert-modal-overlay" onClick={closeModal}>
          <div className="alert-modal" onClick={(e) => e.stopPropagation()}>
            <div className={`alert-modal-header threat-${modalAlert.threat_level || 'none'}`}>
              <div className="modal-title-row">
                {modalAlert.threat_level === 'critical' || modalAlert.threat_level === 'high' ? (
                  <AlertTriangle size={28} className={`icon-threat-${modalAlert.threat_level}`} />
                ) : modalAlert.alert_type === 'known' ? (
                  <User size={28} className="icon-known" />
                ) : (
                  <AlertCircle size={28} className="icon-unknown" />
                )}
                <div className="modal-title-text">
                  <h2>
                    {modalAlert.threat_level && modalAlert.threat_level !== 'none' && (
                      <span className={`threat-badge threat-${modalAlert.threat_level}`}>
                        {modalAlert.threat_level.toUpperCase()}
                      </span>
                    )}
                    {modalAlert.watchlist_status && modalAlert.watchlist_status !== 'normal' && (
                      <span className={`status-badge status-${modalAlert.watchlist_status}`}>
                        {modalAlert.watchlist_status.replace('_', ' ').toUpperCase()}
                      </span>
                    )}
                    {modalAlert.alert_type === 'known' ? modalAlert.person_name : 'Unknown Person Detected'}
                  </h2>
                  <span className="modal-timestamp">{formatTime(modalAlert.timestamp)}</span>
                </div>
              </div>
              <button className="modal-close-btn" onClick={closeModal}>
                <X size={24} />
              </button>
              {/* Queue indicator */}
              {alertQueue.length > 0 && (
                <div className="queue-indicator">
                  <Bell size={16} />
                  <span>{alertQueue.length} more alert{alertQueue.length > 1 ? 's' : ''} pending</span>
                </div>
              )}
            </div>

            {/* Guard Prompt */}
            {modalAlert.displayed_prompt && (
              <div className="modal-guard-prompt">
                <Shield size={18} />
                <span>{modalAlert.displayed_prompt}</span>
              </div>
            )}

            {/* Image Comparison - Large Side by Side */}
            <div className="modal-image-comparison">
              <div className="modal-image-panel enrolled">
                <div className="modal-image-label">ENROLLED PHOTO</div>
                <div className="modal-image-container">
                  {modalAlert.person_id ? (
                    <img
                      src={getPersonImageUrl(modalAlert.person_id)}
                      alt="Enrolled reference"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  ) : (
                    <div className="no-image">
                      <User size={48} />
                      <span>No enrolled photo</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="modal-vs-divider">
                <div className="vs-circle">VS</div>
                <div className="match-score">
                  <span className="score-value">{((modalAlert.similarity_score || modalAlert.confidence) * 100).toFixed(1)}%</span>
                  <span className="score-label">Match</span>
                </div>
              </div>

              <div className="modal-image-panel captured">
                <div className="modal-image-label">CAPTURED NOW</div>
                <div className="modal-image-container">
                  <img
                    src={alertsApi.getSnapshotUrl(modalAlert.id)}
                    alt="Captured snapshot"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Guard Decision Buttons */}
            <div className="modal-actions">
              {!modalAlert.guard_verified ? (
                <>
                  <div className="actions-section-label">
                    <Siren size={18} />
                    Make a Decision:
                  </div>
                  <div className="modal-action-grid">
                    <button
                      className="modal-action-btn confirm"
                      onClick={() => handleVerify(modalAlert.id, 'confirmed')}
                      disabled={verifying === modalAlert.id}
                    >
                      <CheckCircle size={24} />
                      <span>Confirm Threat</span>
                      <small>Identity verified as threat</small>
                    </button>
                    <button
                      className="modal-action-btn false-alarm"
                      onClick={() => handleVerify(modalAlert.id, 'false_alarm')}
                      disabled={verifying === modalAlert.id}
                    >
                      <XCircle size={24} />
                      <span>False Alarm</span>
                      <small>Dismiss this alert</small>
                    </button>
                    <button
                      className="modal-action-btn backup"
                      onClick={() => handleVerify(modalAlert.id, 'backup_requested')}
                      disabled={verifying === modalAlert.id}
                    >
                      <Phone size={24} />
                      <span>Request Backup</span>
                      <small>Call for assistance</small>
                    </button>
                    <button
                      className="modal-action-btn alarm"
                      onClick={() => handleVerify(modalAlert.id, 'alarm_triggered')}
                      disabled={verifying === modalAlert.id}
                    >
                      <Volume2 size={24} />
                      <span>Trigger Alarm</span>
                      <small>Sound emergency alarm</small>
                    </button>
                    <button
                      className="modal-action-btn door"
                      onClick={() => handleVerify(modalAlert.id, 'door_locked')}
                      disabled={verifying === modalAlert.id}
                    >
                      <DoorClosed size={24} />
                      <span>Lock Down</span>
                      <small>Secure all exits</small>
                    </button>
                  </div>
                </>
              ) : (
                <div className="modal-verified-status">
                  <CheckCircle size={24} />
                  <span>Decision Made: <strong>{modalAlert.guard_action?.replace('_', ' ')}</strong></span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Alert List */}
      <div className={`alert-list ${fullPage ? 'full-page' : ''}`}>
        <div className="alert-header">
          <h3>
            <Bell size={20} /> {fullPage ? 'Alert History' : 'Alerts (24h)'}
          </h3>
          <span className="alert-count">{alerts.filter((a) => !a.acknowledged).length} unread</span>
        </div>

        {/* Filter Toolbar - Only on full page */}
        {fullPage && (
          <div className="alert-filters">
            {/* Search */}
            <div className="filter-search">
              <Search size={18} />
              <input
                type="text"
                placeholder="Search by name..."
                value={filters.search}
                onChange={(e) => setFilters(f => ({ ...f, search: e.target.value }))}
              />
              {filters.search && (
                <button className="clear-search" onClick={() => setFilters(f => ({ ...f, search: '' }))}>
                  <X size={16} />
                </button>
              )}
            </div>

            {/* Time Range */}
            <div className="filter-select">
              <Calendar size={18} />
              <select
                value={filters.timeRange}
                onChange={(e) => setFilters(f => ({ ...f, timeRange: e.target.value }))}
              >
                <option value="all">All Time</option>
                <option value="24h">Last 24 Hours</option>
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
              </select>
            </div>

            {/* Threat Level */}
            <div className="filter-select">
              <Filter size={18} />
              <select
                value={filters.threatLevel}
                onChange={(e) => setFilters(f => ({ ...f, threatLevel: e.target.value }))}
              >
                <option value="">All Levels</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            {/* Actions */}
            <div className="filter-actions">
              <button className="btn btn-icon" onClick={loadAlerts} title="Refresh">
                <RefreshCw size={18} />
              </button>
              <button className="btn btn-export" onClick={handleExportCsv} title="Export to CSV">
                <Download size={18} />
                Export CSV
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="loading">Loading alerts...</div>
        ) : alerts.length === 0 ? (
          <div className="empty">
            {fullPage && (filters.search || filters.timeRange !== 'all' || filters.threatLevel)
              ? 'No alerts match your filters'
              : 'No alerts yet'}
          </div>
        ) : (
          <ul className="alerts">
            {alerts.map((alert) => (
              <li
                key={alert.id}
                className={`alert-item ${alert.acknowledged ? 'acknowledged' : 'unread'} ${alert.alert_type} ${alert.threat_level ? `threat-${alert.threat_level}` : ''}`}
              >
                {/* Main alert row - clickable to open modal */}
                <div className="alert-row" onClick={() => openAlertModal(alert)}>
                  <div className="alert-icon">
                    {alert.threat_level === 'critical' || alert.threat_level === 'high' ? (
                      <AlertTriangle size={24} className={`icon-threat-${alert.threat_level}`} />
                    ) : alert.alert_type === 'known' ? (
                      <User size={24} className="icon-known" />
                    ) : (
                      <AlertCircle size={24} className="icon-unknown" />
                    )}
                  </div>

                  <div className="alert-content">
                    <div className="alert-title">
                      {alert.threat_level && alert.threat_level !== 'none' && (
                        <span className={`threat-badge threat-${alert.threat_level}`}>
                          {alert.threat_level.toUpperCase()}
                        </span>
                      )}
                      {alert.watchlist_status && alert.watchlist_status !== 'normal' && (
                        <span className={`status-badge status-${alert.watchlist_status}`}>
                          {alert.watchlist_status.replace('_', ' ').toUpperCase()}
                        </span>
                      )}
                      {alert.alert_type === 'known'
                        ? `${alert.person_name}`
                        : 'Unknown Person'}
                    </div>

                    <div className="alert-meta">
                      <span className="alert-time">{formatTime(alert.timestamp)}</span>
                      <span className="alert-confidence">
                        {alert.similarity_score
                          ? `Match: ${(alert.similarity_score * 100).toFixed(1)}%`
                          : `Conf: ${(alert.confidence * 100).toFixed(1)}%`}
                      </span>
                      {alert.guard_verified && (
                        <span className={`guard-verified action-${alert.guard_action}`}>
                          {alert.guard_action?.replace('_', ' ')}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="alert-actions">
                    {!alert.acknowledged && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleAcknowledge(alert.id); }}
                        className="ack-btn"
                        title="Acknowledge"
                      >
                        <Check size={16} />
                      </button>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(alert.id); }}
                      className="delete-btn"
                      title="Delete"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

export default AlertList;
