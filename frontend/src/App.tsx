import { useState } from 'react';
import { LiveStream } from './components/LiveStream';
import { MultiCameraView } from './components/MultiCameraView';
import { PersonList } from './components/PersonList';
import { AlertList } from './components/AlertList';
import { SystemStatus } from './components/SystemStatus';
import { SystemSettings } from './components/SystemSettings';
import { CameraList } from './components/CameraList';
import { Monitor, Users, Bell, Settings, Camera, Grid, Video } from 'lucide-react';
import './App.css';

type Tab = 'dashboard' | 'persons' | 'alerts' | 'cameras' | 'settings';
type DashboardView = 'single' | 'multi';

function App() {
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

export default App;
