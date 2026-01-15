import { useState, useEffect } from 'react';
import { LiveStream } from './components/LiveStream';
import { MultiCameraView } from './components/MultiCameraView';
import { PersonList } from './components/PersonList';
import { AlertList } from './components/AlertList';
import { SystemStatus } from './components/SystemStatus';
import { SystemSettings } from './components/SystemSettings';
import { CameraList } from './components/CameraList';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Monitor, Users, Bell, Settings, Camera, Grid, Video, LogOut } from 'lucide-react';
import './App.css';

type Tab = 'dashboard' | 'persons' | 'alerts' | 'cameras' | 'settings';
type DashboardView = 'single' | 'multi';

// Login component
function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <h1>Face Recognition System</h1>
        <h2>Login</h2>
        <form onSubmit={handleSubmit}>
          {error && <div className="login-error">{error}</div>}
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" disabled={isLoading} className="login-button">
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
}

// Main app component
function MainApp() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [dashboardView, setDashboardView] = useState<DashboardView>('single');

  return (
    <div className="app">
      <header className="app-header">
        <h1>Face Recognition Security System</h1>
        <nav className="nav-tabs">
          <button
            className={activeTab === 'dashboard' ? 'active' : ''}
            onClick={() => setActiveTab('dashboard')}
          >
            <Monitor size={18} />
            Dashboard
          </button>
          <button
            className={activeTab === 'persons' ? 'active' : ''}
            onClick={() => setActiveTab('persons')}
          >
            <Users size={18} />
            Persons
          </button>
          <button
            className={activeTab === 'alerts' ? 'active' : ''}
            onClick={() => setActiveTab('alerts')}
          >
            <Bell size={18} />
            Alerts
          </button>
          <button
            className={activeTab === 'cameras' ? 'active' : ''}
            onClick={() => setActiveTab('cameras')}
          >
            <Camera size={18} />
            Cameras
          </button>
          <button
            className={activeTab === 'settings' ? 'active' : ''}
            onClick={() => setActiveTab('settings')}
          >
            <Settings size={18} />
            Settings
          </button>
        </nav>
        <div className="user-menu">
          <span className="user-name">{user?.username}</span>
          <button onClick={logout} className="logout-button" title="Logout">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <main className="app-content">
        {activeTab === 'dashboard' && (
          <div className="dashboard">
            <div className="dashboard-main">
              <div className="view-toggle">
                <button
                  className={dashboardView === 'single' ? 'active' : ''}
                  onClick={() => setDashboardView('single')}
                  title="Single Camera View"
                >
                  <Video size={16} />
                  Single
                </button>
                <button
                  className={dashboardView === 'multi' ? 'active' : ''}
                  onClick={() => setDashboardView('multi')}
                  title="Multi-Camera Grid"
                >
                  <Grid size={16} />
                  Multi
                </button>
              </div>
              {dashboardView === 'single' ? (
                <LiveStream autoStart={true} />
              ) : (
                <MultiCameraView />
              )}
            </div>
            <div className="dashboard-sidebar">
              <SystemStatus />
              <AlertList />
            </div>
          </div>
        )}

        {activeTab === 'persons' && (
          <div className="persons-page">
            <PersonList />
          </div>
        )}

        {activeTab === 'alerts' && (
          <div className="alerts-page">
            <AlertList fullPage={true} />
          </div>
        )}

        {activeTab === 'cameras' && (
          <div className="cameras-page">
            <CameraList />
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="settings-page">
            <SystemSettings />
          </div>
        )}
      </main>

      <footer className="app-footer">
        <span>Face Recognition Security System - Jetson Orin Nano 8GB</span>
      </footer>
    </div>
  );
}

// App wrapper with auth
function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();

  // Listen for auth:logout events (from API interceptor)
  useEffect(() => {
    const handleLogout = () => {
      window.location.reload();
    };
    window.addEventListener('auth:logout', handleLogout);
    return () => window.removeEventListener('auth:logout', handleLogout);
  }, []);

  if (isLoading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  return isAuthenticated ? <MainApp /> : <LoginPage />;
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
