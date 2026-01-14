import { useEffect, useState, useRef, useCallback } from 'react';
import { personsApi, streamApi, camerasApi, getPersonImageUrl } from '../services/api';
import { Trash2, UserPlus, Image, Camera, X, CameraIcon, RefreshCw, Search, User, Calendar, Eye, Shield, AlertTriangle } from 'lucide-react';
import axios from 'axios';

interface Person {
  id: number;
  name: string;
  id_card?: string;
  case?: string;
  embedding_count: number;
  watchlist_status?: string;
  threat_level?: string;
  created_at?: string;
}

interface PersonDetails {
  id: number;
  name: string;
  id_card?: string;
  case?: string;
  embedding_count: number;
  watchlist_status?: string;
  threat_level?: string;
  guard_prompt?: string;
  created_at?: string;
  updated_at?: string;
  detection_count: number;
  last_detection?: string;
  has_reference_image: boolean;
}

interface CameraInfo {
  id: number;
  name: string;
  ip_address: string;
  enabled: boolean;
}

export function PersonList() {
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showCameraModal, setShowCameraModal] = useState(false);
  const [streamKey, setStreamKey] = useState(Date.now());
  const streamRef = useRef<HTMLImageElement>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Person details modal
  const [selectedPerson, setSelectedPerson] = useState<PersonDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  // Form fields
  const [enrollName, setEnrollName] = useState('');
  const [enrollIdCard, setEnrollIdCard] = useState('');
  const [enrollCase, setEnrollCase] = useState('');
  const [enrollFile, setEnrollFile] = useState<File | null>(null);
  const [watchlistStatus, setWatchlistStatus] = useState('criminal');
  const [threatLevel, setThreatLevel] = useState('high');

  // Camera capture state - capture first, then fill details
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [captureStep, setCaptureStep] = useState<'preview' | 'details'>('preview');

  // Camera selection for enrollment
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load persons when search changes
  useEffect(() => {
    loadPersons(debouncedSearch);
  }, [debouncedSearch]);

  const loadPersons = useCallback(async (search?: string) => {
    try {
      setLoading(true);
      const response = await personsApi.list(search || undefined);
      setPersons(response.data);
    } catch (err) {
      console.error('Failed to load persons:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const openPersonDetails = async (personId: number) => {
    try {
      setLoadingDetails(true);
      const response = await personsApi.getDetails(personId);
      setSelectedPerson(response.data);
    } catch (err) {
      console.error('Failed to load person details:', err);
      showMessage('error', 'Failed to load person details');
    } finally {
      setLoadingDetails(false);
    }
  };

  const closePersonDetails = () => {
    setSelectedPerson(null);
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  const resetForm = () => {
    setEnrollName('');
    setEnrollIdCard('');
    setEnrollCase('');
    setEnrollFile(null);
    setWatchlistStatus('criminal');
    setThreatLevel('high');
    setCapturedImage(null);
    setCaptureStep('preview');
    // Reset file input
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    if (fileInput) fileInput.value = '';
  };

  // Handle file-based enrollment
  const handleEnroll = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!enrollName.trim()) {
      showMessage('error', 'Name is required');
      return;
    }
    if (!enrollFile) {
      showMessage('error', 'Please select an image file');
      return;
    }

    try {
      setEnrolling(true);
      setMessage(null);
      await personsApi.enroll(
        enrollName.trim(),
        enrollFile,
        enrollIdCard.trim() || undefined,
        enrollCase.trim() || undefined,
        watchlistStatus,
        threatLevel
      );
      showMessage('success', `Successfully enrolled ${enrollName}!`);
      resetForm();
      loadPersons(debouncedSearch);
    } catch (err) {
      console.error('Enrollment failed:', err);
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        showMessage('error', err.response.data.detail);
      } else {
        showMessage('error', 'Enrollment failed. Make sure a clear face is visible.');
      }
    } finally {
      setEnrolling(false);
    }
  };

  // Open camera modal directly - no details required first
  const openCameraEnroll = async () => {
    try {
      await streamApi.start();
    } catch (err) {
      console.log('Stream may already be running');
    }

    // Fetch available cameras
    try {
      const response = await camerasApi.list(true); // Only enabled cameras
      const enabledCameras = response.data;
      setCameras(enabledCameras);
      // Default to first camera
      if (enabledCameras.length > 0) {
        setSelectedCameraId(enabledCameras[0].id);
      }
    } catch (err) {
      console.error('Failed to load cameras:', err);
    }

    setCapturedImage(null);
    setCaptureStep('preview');
    setStreamKey(Date.now());
    setShowCameraModal(true);
  };

  // Capture snapshot from stream - just get the image, don't enroll yet
  const handleCaptureSnapshot = async () => {
    try {
      // Get current frame as snapshot from selected camera (raw, no overlays)
      const snapshotUrl = selectedCameraId
        ? streamApi.getCameraSnapshotUrl(selectedCameraId)
        : streamApi.getSnapshotUrl();
      const response = await fetch(`${snapshotUrl}?t=${Date.now()}`);
      if (!response.ok) throw new Error('Failed to capture snapshot');
      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);
      setCapturedImage(imageUrl);
      setCaptureStep('details');
    } catch (err) {
      console.error('Snapshot capture failed:', err);
      showMessage('error', 'Failed to capture snapshot. Please try again.');
    }
  };

  // After filling details, enroll the person
  const handleCameraEnroll = async () => {
    if (!enrollName.trim()) {
      showMessage('error', 'Name is required');
      return;
    }

    if (!selectedCameraId) {
      showMessage('error', 'Please select a camera');
      return;
    }

    try {
      setEnrolling(true);
      setMessage(null);

      await personsApi.enrollFromCamera(
        enrollName.trim(),
        enrollIdCard.trim() || undefined,
        enrollCase.trim() || undefined,
        watchlistStatus,
        threatLevel,
        selectedCameraId  // Pass selected camera ID
      );
      showMessage('success', `Successfully enrolled ${enrollName}!`);

      setShowCameraModal(false);
      resetForm();
      loadPersons(debouncedSearch);
    } catch (err) {
      console.error('Camera enrollment failed:', err);
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        showMessage('error', err.response.data.detail);
      } else {
        showMessage('error', 'Enrollment failed. Make sure a clear face is visible.');
      }
    } finally {
      setEnrolling(false);
    }
  };

  // Go back to preview step
  const handleRetake = () => {
    setCapturedImage(null);
    setCaptureStep('preview');
    setStreamKey(Date.now());
  };

  const closeCameraModal = () => {
    setShowCameraModal(false);
  };

  const refreshStream = () => {
    setStreamKey(Date.now());
  };

  const handleDelete = async (personId: number) => {
    if (!confirm('Are you sure you want to delete this person?')) return;

    try {
      await personsApi.delete(personId);
      loadPersons();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleAddImage = async (personId: number, file: File) => {
    try {
      await personsApi.addImage(personId, file);
      showMessage('success', 'Image added successfully');
      loadPersons();
    } catch (err) {
      console.error('Add image failed:', err);
      showMessage('error', 'Failed to add image. Make sure it contains a clear face.');
    }
  };

  return (
    <>
      {/* Person Details Modal */}
      {selectedPerson && (
        <div className="person-modal-overlay" onClick={closePersonDetails}>
          <div className="person-modal" onClick={(e) => e.stopPropagation()}>
            <div className={`person-modal-header threat-${selectedPerson.threat_level || 'none'}`}>
              <div className="modal-title-row">
                {selectedPerson.threat_level && selectedPerson.threat_level !== 'none' ? (
                  <AlertTriangle size={28} className={`icon-threat-${selectedPerson.threat_level}`} />
                ) : (
                  <User size={28} />
                )}
                <div className="modal-title-text">
                  <h2>
                    {selectedPerson.threat_level && selectedPerson.threat_level !== 'none' && (
                      <span className={`threat-badge threat-${selectedPerson.threat_level}`}>
                        {selectedPerson.threat_level.toUpperCase()}
                      </span>
                    )}
                    {selectedPerson.watchlist_status && selectedPerson.watchlist_status !== 'normal' && (
                      <span className={`status-badge status-${selectedPerson.watchlist_status}`}>
                        {selectedPerson.watchlist_status.replace('_', ' ').toUpperCase()}
                      </span>
                    )}
                    {selectedPerson.name}
                  </h2>
                </div>
              </div>
              <button className="modal-close-btn" onClick={closePersonDetails}>
                <X size={24} />
              </button>
            </div>

            <div className="person-modal-body">
              {/* Photo Section */}
              <div className="person-photo-section">
                {selectedPerson.has_reference_image ? (
                  <img
                    src={getPersonImageUrl(selectedPerson.id)}
                    alt={selectedPerson.name}
                    className="person-photo"
                  />
                ) : (
                  <div className="no-photo">
                    <User size={64} />
                    <span>No photo</span>
                  </div>
                )}
              </div>

              {/* Details Section */}
              <div className="person-details-section">
                <div className="detail-row">
                  <span className="detail-label">ID Card:</span>
                  <span className="detail-value">{selectedPerson.id_card || 'N/A'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Case/Notes:</span>
                  <span className="detail-value">{selectedPerson.case || 'N/A'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Enrolled Images:</span>
                  <span className="detail-value">{selectedPerson.embedding_count}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Enrolled On:</span>
                  <span className="detail-value">{formatDate(selectedPerson.created_at)}</span>
                </div>
                {selectedPerson.guard_prompt && (
                  <div className="detail-row guard-prompt">
                    <Shield size={16} />
                    <span className="detail-value">{selectedPerson.guard_prompt}</span>
                  </div>
                )}
              </div>

              {/* Detection Stats */}
              <div className="person-stats-section">
                <h4><Eye size={18} /> Detection Statistics</h4>
                <div className="stats-grid">
                  <div className="stat-card">
                    <span className="stat-value">{selectedPerson.detection_count}</span>
                    <span className="stat-label">Total Detections</span>
                  </div>
                  <div className="stat-card">
                    <Calendar size={16} />
                    <span className="stat-label">Last Detected</span>
                    <span className="stat-value small">{formatDate(selectedPerson.last_detection)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="person-modal-footer">
              <button className="btn btn-secondary" onClick={closePersonDetails}>
                Close
              </button>
              <button
                className="btn btn-danger"
                onClick={() => {
                  if (confirm('Are you sure you want to delete this person?')) {
                    handleDelete(selectedPerson.id);
                    closePersonDetails();
                  }
                }}
              >
                <Trash2 size={16} />
                Delete Person
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Camera Capture Modal - Two Steps: Preview -> Details */}
      {showCameraModal && (
        <div className="camera-modal-overlay" onClick={closeCameraModal}>
          <div className="camera-modal" onClick={(e) => e.stopPropagation()}>
            <div className="camera-modal-header">
              <h2>
                <CameraIcon size={24} />
                {captureStep === 'preview' ? 'Capture Photo' : 'Enter Details'}
              </h2>
              <button className="modal-close-btn" onClick={closeCameraModal}>
                <X size={24} />
              </button>
            </div>

            <div className="camera-modal-body">
              {captureStep === 'preview' ? (
                /* Step 1: Live Preview - Capture */
                <>
                  {/* Camera Selector */}
                  <div className="camera-selector">
                    <label>Select Camera:</label>
                    <select
                      value={selectedCameraId || ''}
                      onChange={(e) => {
                        setSelectedCameraId(Number(e.target.value));
                        setStreamKey(Date.now()); // Refresh stream when camera changes
                      }}
                      className="camera-select"
                    >
                      {cameras.map((cam) => (
                        <option key={cam.id} value={cam.id}>
                          {cam.name} ({cam.ip_address})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="camera-preview">
                    <img
                      key={streamKey}
                      ref={streamRef}
                      src={selectedCameraId
                        ? `${streamApi.getCameraRawMjpegUrl(selectedCameraId)}?t=${streamKey}`
                        : `${streamApi.getRawMjpegUrl()}?t=${streamKey}`
                      }
                      alt="Camera Preview"
                      className="camera-stream"
                    />
                    <div className="face-guide">
                      <div className="face-oval"></div>
                      <span>Face can be anywhere in frame</span>
                    </div>
                    <button className="stream-refresh-btn" onClick={refreshStream} title="Refresh stream">
                      <RefreshCw size={18} />
                    </button>
                  </div>
                  <p className="capture-hint">
                    Position the person's face clearly in <strong>{cameras.find(c => c.id === selectedCameraId)?.name || 'camera'}</strong>, then click Capture
                  </p>
                </>
              ) : (
                /* Step 2: Show captured image + Enter details */
                <div className="capture-details-container">
                  <div className="captured-image-section">
                    {capturedImage && (
                      <img src={capturedImage} alt="Captured" className="captured-image" />
                    )}
                    <button className="btn btn-secondary retake-btn" onClick={handleRetake}>
                      <RefreshCw size={16} />
                      Retake
                    </button>
                  </div>

                  <div className="capture-form-section">
                    <div className="form-group">
                      <label>Name *</label>
                      <input
                        type="text"
                        placeholder="Enter person's name"
                        value={enrollName}
                        onChange={(e) => setEnrollName(e.target.value)}
                        autoFocus
                      />
                    </div>
                    <div className="form-group">
                      <label>ID Card</label>
                      <input
                        type="text"
                        placeholder="ID card number"
                        value={enrollIdCard}
                        onChange={(e) => setEnrollIdCard(e.target.value)}
                      />
                    </div>
                    <div className="form-group">
                      <label>Case / Notes</label>
                      <input
                        type="text"
                        placeholder="Case details or notes"
                        value={enrollCase}
                        onChange={(e) => setEnrollCase(e.target.value)}
                      />
                    </div>
                    <div className="form-row-inline">
                      <div className="form-group">
                        <label>Status</label>
                        <select
                          value={watchlistStatus}
                          onChange={(e) => setWatchlistStatus(e.target.value)}
                        >
                          <option value="criminal">Criminal</option>
                          <option value="most_wanted">Most Wanted</option>
                          <option value="suspect">Suspect</option>
                          <option value="person_of_interest">Person of Interest</option>
                          <option value="banned">Banned</option>
                          <option value="vip">VIP</option>
                          <option value="normal">Normal</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Threat Level</label>
                        <select
                          value={threatLevel}
                          onChange={(e) => setThreatLevel(e.target.value)}
                        >
                          <option value="critical">Critical</option>
                          <option value="high">High</option>
                          <option value="medium">Medium</option>
                          <option value="low">Low</option>
                          <option value="none">None</option>
                        </select>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="camera-modal-footer">
              <button className="btn btn-secondary" onClick={closeCameraModal}>
                Cancel
              </button>
              {captureStep === 'preview' ? (
                <button
                  className="btn btn-primary capture-btn"
                  onClick={handleCaptureSnapshot}
                >
                  <Camera size={20} />
                  Capture
                </button>
              ) : (
                <button
                  className="btn btn-primary enroll-btn"
                  onClick={handleCameraEnroll}
                  disabled={enrolling || !enrollName.trim()}
                >
                  <UserPlus size={20} />
                  {enrolling ? 'Enrolling...' : 'Enroll Person'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="person-list">
        <h3>Enrolled Persons</h3>

        {/* Search Bar */}
        <div className="search-bar">
          <Search size={18} />
          <input
            type="text"
            placeholder="Search by name or ID card..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
          />
          {searchQuery && (
            <button className="clear-search" onClick={() => setSearchQuery('')}>
              <X size={16} />
            </button>
          )}
        </div>

        {/* Message Display */}
        {message && (
          <div className={`enroll-message ${message.type}`}>
            {message.text}
          </div>
        )}

        {/* Enrollment Options */}
        <div className="enroll-options">
          {/* Camera Enroll Button - Quick action */}
          <button
            type="button"
            className="btn btn-primary camera-enroll-btn"
            onClick={openCameraEnroll}
          >
            <Camera size={20} />
            Enroll from Camera
          </button>

          {/* File Upload Form */}
          <form onSubmit={handleEnroll} className="enroll-form file-enroll">
            <div className="form-header">
              <Image size={16} />
              <span>Or enroll from file:</span>
            </div>
            <div className="form-row">
              <input
                type="text"
                placeholder="Name *"
                value={enrollName}
                onChange={(e) => setEnrollName(e.target.value)}
              />
              <input
                type="text"
                placeholder="ID Card"
                value={enrollIdCard}
                onChange={(e) => setEnrollIdCard(e.target.value)}
              />
            </div>
            <div className="form-row">
              <select
                value={watchlistStatus}
                onChange={(e) => setWatchlistStatus(e.target.value)}
                className="form-select"
              >
                <option value="criminal">Criminal</option>
                <option value="most_wanted">Most Wanted</option>
                <option value="suspect">Suspect</option>
                <option value="person_of_interest">Person of Interest</option>
                <option value="banned">Banned</option>
                <option value="vip">VIP</option>
                <option value="normal">Normal</option>
              </select>
              <select
                value={threatLevel}
                onChange={(e) => setThreatLevel(e.target.value)}
                className="form-select"
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="none">None</option>
              </select>
            </div>
            <div className="form-row">
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setEnrollFile(e.target.files?.[0] || null)}
              />
              <button
                type="submit"
                disabled={enrolling || !enrollName.trim() || !enrollFile}
                className="enroll-btn"
              >
                <UserPlus size={16} />
                {enrolling ? 'Enrolling...' : 'Enroll'}
              </button>
            </div>
          </form>
        </div>

      {/* Person List */}
      {loading ? (
        <div className="loading">Loading...</div>
      ) : persons.length === 0 ? (
        <div className="empty">
          {searchQuery ? `No persons found matching "${searchQuery}"` : 'No persons enrolled yet'}
        </div>
      ) : (
        <ul className="persons">
          {persons.map((person) => (
            <li
              key={person.id}
              className={`person-item ${person.threat_level ? `threat-${person.threat_level}` : ''}`}
              onClick={() => openPersonDetails(person.id)}
            >
              <div className="person-info">
                <div className="person-name-row">
                  {person.threat_level && person.threat_level !== 'none' && (
                    <span className={`threat-badge small threat-${person.threat_level}`}>
                      {person.threat_level.toUpperCase()}
                    </span>
                  )}
                  {person.watchlist_status && person.watchlist_status !== 'normal' && (
                    <span className={`status-badge small status-${person.watchlist_status}`}>
                      {person.watchlist_status.replace('_', ' ').toUpperCase()}
                    </span>
                  )}
                  <span className="person-name">{person.name}</span>
                </div>
                {person.id_card && (
                  <span className="person-meta">ID: {person.id_card}</span>
                )}
                {person.case && (
                  <span className="person-meta">Case: {person.case}</span>
                )}
                <span className="embedding-count">{person.embedding_count} image(s)</span>
              </div>
              <div className="person-actions">
                <label className="add-image-btn" title="Add more images" onClick={(e) => e.stopPropagation()}>
                  <Image size={16} />
                  <input
                    type="file"
                    accept="image/*"
                    hidden
                    onChange={(e) => {
                      if (e.target.files?.[0]) {
                        handleAddImage(person.id, e.target.files[0]);
                      }
                    }}
                  />
                </label>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(person.id); }}
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
      {loadingDetails && (
        <div className="loading-overlay">
          <div className="loading-spinner">Loading details...</div>
        </div>
      )}
      </div>
    </>
  );
}

export default PersonList;
