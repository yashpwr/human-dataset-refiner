import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ErrorBanner from './components/ErrorBanner';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import JobDetail from './pages/JobDetail';
import Datasets from './pages/Datasets';
import DatasetDetail from './pages/DatasetDetail';
import Report from './pages/Report';
import './index.css';
import './App.css';

function AppContent() {
  const [theme, setTheme] = useState('dark');
  const [error, setError] = useState('');
  const routerNavigate = useNavigate();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  // Unified navigate helper to maintain compatibility with existing components
  const navigate = (path, state = {}) => {
    // If path is a view name (legacy), map it to a URL
    const routeMap = {
      'dashboard': '/',
      'jobs': '/jobs',
      'job-detail': '/job-detail', // Will be handled by ID-based routes
      'datasets': '/datasets',
      'dataset-detail': '/dataset-detail',
      'report': '/report'
    };
    const target = routeMap[path] || path;
    routerNavigate(target, { state });
  };

  return (
    <div className="app-container">
      <Sidebar
        theme={theme}
        toggleTheme={toggleTheme}
      />
      <main className="main-content">
        <ErrorBanner message={error} />
        <Routes>
          <Route path="/" element={<Dashboard navigate={navigate} />} />
          <Route path="/jobs" element={<Jobs navigate={navigate} />} />
          <Route path="/jobs/:jobId" element={<JobDetail navigate={navigate} />} />
          <Route path="/datasets" element={<Datasets navigate={navigate} />} />
          <Route path="/datasets/:datasetId" element={<DatasetDetail navigate={navigate} />} />
          <Route path="/report" element={<Report />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
