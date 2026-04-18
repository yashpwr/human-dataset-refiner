import { useState, useEffect } from 'react';
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

function App() {
  const [theme, setTheme] = useState('dark');
  const [currentView, setCurrentView] = useState('dashboard');
  const [error, setError] = useState('');
  const [selectedJob, setSelectedJob] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState(null);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  const navigate = (view) => setCurrentView(view);

  return (
    <div className="app-container">
      <Sidebar
        currentView={currentView}
        setCurrentView={setCurrentView}
        theme={theme}
        toggleTheme={toggleTheme}
      />
      <main className="main-content">
        <ErrorBanner message={error} />
        {currentView === 'dashboard' && <Dashboard navigate={navigate} />}
        {currentView === 'jobs' && (
          <Jobs navigate={navigate} setSelectedJob={setSelectedJob} />
        )}
        {currentView === 'job-detail' && selectedJob && (
          <JobDetail job={selectedJob} navigate={navigate} />
        )}
        {currentView === 'datasets' && (
          <Datasets navigate={navigate} setSelectedDataset={setSelectedDataset} />
        )}
        {currentView === 'dataset-detail' && selectedDataset && (
          <DatasetDetail dataset={selectedDataset} navigate={navigate} />
        )}
        {currentView === 'report' && <Report />}
      </main>
    </div>
  );
}

export default App;
