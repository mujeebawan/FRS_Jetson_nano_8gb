import { useState } from 'react';
import { LiveStream } from './components/LiveStream';
import { PersonList } from './components/PersonList';
import { AlertList } from './components/AlertList';
import { SystemStatus } from './components/SystemStatus';
import { Monitor, Users, Bell, Settings } from 'lucide-react';
import './App.css';

type Tab = 'dashboard' | 'persons' | 'alerts' | 'settings';

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

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
              <LiveStream autoStart={true} />
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
            <AlertList />
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="settings-page">
            <h2>Settings</h2>
            <p>Settings panel coming soon...</p>
            <SystemStatus />
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
