import { useState, useEffect } from 'react';
import { Play, Loader2, RefreshCw, Plus } from 'lucide-react';
import Stepper from '../components/Stepper';
import Modal from '../components/Modal';
import { listJobs, getJob, startJob, createJob } from '../api';

export default function Dashboard({ navigate }) {
  const [jobs, setJobs] = useState([]);
  const [activeJob, setActiveJob] = useState(null);
  const [isPromptOpen, setIsPromptOpen] = useState(false);
  const [newJobName, setNewJobName] = useState('');

  const fetchJobs = async () => {
    try {
      const data = await listJobs();
      setJobs(data);
      // Find running or most recently completed job
      const running = data.find(j => j.status === 'running');
      if (running) {
        setActiveJob(running);
      } else {
        const completed = data.find(j => j.status === 'completed');
        if (completed && (!activeJob || activeJob.status === 'running')) {
          setActiveJob(completed);
        }
      }
    } catch (err) {}
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, activeJob?.status === 'running' ? 500 : 3000);
    return () => clearInterval(interval);
  }, [activeJob?.status]);

  // Refresh activeJob specifically when running
  useEffect(() => {
    if (!activeJob?.id || activeJob.status !== 'running') return;
    const interval = setInterval(async () => {
      try {
        const job = await getJob(activeJob.id);
        setActiveJob(job);
      } catch (err) {}
    }, 500);
    return () => clearInterval(interval);
  }, [activeJob?.id, activeJob?.status]);

  const handleNewJob = async (e) => {
    e.preventDefault();
    if (!newJobName.trim()) return;
    try {
      await createJob(newJobName.trim());
      setIsPromptOpen(false);
      setNewJobName('');
      fetchJobs();
      navigate('jobs');
    } catch (err) {
      alert(err.message);
    }
  };

  const isRunning = activeJob?.status === 'running';
  const isComplete = activeJob?.status === 'completed';

  return (
    <div className="animate-fade-in">
      <div className="view-header">
        <h2>Console Dashboard</h2>
        <p>Monitor pipeline status and manage jobs.</p>
      </div>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        <button className="btn" onClick={() => setIsPromptOpen(true)}>
          <Plus size={16} /> New Job
        </button>
        <button className="btn btn-secondary" onClick={() => navigate('/jobs')}>
          View All Jobs
        </button>
      </div>

      <Modal isOpen={isPromptOpen} onClose={() => setIsPromptOpen(false)} title="Create New Job">
        <form onSubmit={handleNewJob}>
          <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>Job Name</label>
          <input 
            type="text" 
            autoFocus
            value={newJobName} 
            onChange={e => setNewJobName(e.target.value)}
            placeholder="e.g., john_doe_photos"
            style={{ 
              width: '100%', padding: '0.75rem', borderRadius: '4px', border: '1px solid var(--surface-border)',
              background: 'var(--bg-color)', color: 'var(--text-main)', marginBottom: '1.5rem', fontSize: '1rem'
            }} 
          />
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-secondary" onClick={() => setIsPromptOpen(false)}>Cancel</button>
            <button type="submit" className="btn" disabled={!newJobName.trim()}>Create</button>
          </div>
        </form>
      </Modal>

      {activeJob && (
        <div className="glass-panel status-panel">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            Pipeline Status — {activeJob.name}
            {isRunning && <RefreshCw size={16} className="animate-pulse" color="var(--primary-color)" />}
          </h3>

          <div className="mono" style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            State: <span style={{ color: 'var(--text-main)' }}>{activeJob.status?.toUpperCase()}</span><br/>
            Current Step: <span style={{ color: 'var(--text-main)' }}>{activeJob.current_step || 'Awaiting task'}</span><br/>
            Total Images: <span style={{ color: 'var(--text-main)' }}>{activeJob.total_images || activeJob.image_count || 0}</span>
          </div>

          {(isRunning || isComplete) && (
            <Stepper
              progress={activeJob.progress || 0}
              currentStep={activeJob.current_step || ''}
              isComplete={isComplete}
            />
          )}

          {activeJob.status === 'failed' && (
            <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'rgba(239,68,68,0.1)', borderRadius: 'var(--radius)', color: 'var(--error-color)', fontSize: '0.85rem' }}>
              Error: {activeJob.error}
            </div>
          )}
        </div>
      )}

      {!activeJob && (
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          No jobs yet. Create a new job to get started.
        </div>
      )}
    </div>
  );
}
