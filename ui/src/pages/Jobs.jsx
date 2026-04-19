import { useState, useEffect } from 'react';
import { Plus, Settings2, ChevronDown, ChevronUp, HelpCircle, Zap, Maximize, Users, Repeat } from 'lucide-react';
import FolderCard from '../components/FolderCard';
import Modal from '../components/Modal';
import { listJobs, createJob, deleteJob, renameJob } from '../api';

const STATUS_COLORS = {
  idle: 'var(--text-muted)',
  running: 'var(--primary-color)',
  completed: 'var(--success-color)',
  failed: 'var(--error-color)',
};

const DEFAULT_CONFIG = {
  blur_threshold: 35.0,
  min_resolution: 64,
  face_distance_threshold: 0.55,
  phash_threshold: 8,
  enable_quality_check: true,
  enable_duplicate_check: true,
  face_confidence: 0.6,
  min_face_size: 50,
};

export default function Jobs({ navigate, setSelectedJob }) {
  const [jobs, setJobs] = useState([]);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newJobName, setNewJobName] = useState('');
  const [config, setConfig] = useState({ ...DEFAULT_CONFIG });

  const [jobToDelete, setJobToDelete] = useState(null);
  const [jobToRename, setJobToRename] = useState(null);
  const [renameJobName, setRenameJobName] = useState('');

  const fetchJobs = async () => {
    try { setJobs(await listJobs()); } catch (err) { }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newJobName.trim()) return;
    try {
      const job = await createJob(newJobName.trim());
      setIsCreateOpen(false);
      setNewJobName('');
      fetchJobs();
      navigate(`/jobs/${job.id}`);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleConfigChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleDelete = async () => {
    if (!jobToDelete) return;
    try {
      await deleteJob(jobToDelete.id);
      setJobToDelete(null);
      fetchJobs();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleRename = async (e) => {
    e.preventDefault();
    if (!renameJobName.trim() || !jobToRename) return;
    try {
      await renameJob(jobToRename.id, renameJobName.trim());
      setJobToRename(null);
      setRenameJobName('');
      fetchJobs();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="animate-fade-in">
      <div className="view-header">
        <h2>Jobs</h2>
        <p>Each job contains a dataset, clusters, and removed images.</p>
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <button className="btn" onClick={() => setIsCreateOpen(true)}>
          <Plus size={16} /> New Job
        </button>
      </div>

      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Create New Job">
        <form onSubmit={handleCreate} style={{ width: '450px', maxWidth: '100%' }}>
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Job Name</label>
            <input
              type="text" autoFocus value={newJobName} onChange={e => setNewJobName(e.target.value)}
              placeholder="e.g., ranveer_portraits"
              style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--surface-border)', background: 'var(--bg-color)', color: 'var(--text-main)', fontSize: '1rem' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
            <button type="button" className="btn btn-secondary" onClick={() => setIsCreateOpen(false)}>Cancel</button>
            <button type="submit" className="btn" disabled={!newJobName.trim()}>Create Job</button>
          </div>
        </form>
      </Modal>

      <Modal isOpen={!!jobToDelete} onClose={() => setJobToDelete(null)} title="Delete Job">
        <p style={{ marginBottom: '1.5rem' }}>Are you sure you want to delete <strong>{jobToDelete?.name}</strong>? This will permanently delete all data associated with this job.</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={() => setJobToDelete(null)}>Cancel</button>
          <button className="btn btn-danger" onClick={handleDelete}>Delete Permanently</button>
        </div>
      </Modal>

      <Modal isOpen={!!jobToRename} onClose={() => setJobToRename(null)} title="Rename Job">
        <form onSubmit={handleRename}>
          <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>New Job Name</label>
          <input
            type="text" autoFocus value={renameJobName} onChange={e => setRenameJobName(e.target.value)}
            style={{ width: '100%', padding: '0.75rem', borderRadius: '4px', border: '1px solid var(--surface-border)', background: 'var(--bg-color)', color: 'var(--text-main)', marginBottom: '1.5rem', fontSize: '1rem' }}
          />
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-secondary" onClick={() => setJobToRename(null)}>Cancel</button>
            <button type="submit" className="btn" disabled={!renameJobName.trim()}>Rename</button>
          </div>
        </form>
      </Modal>

      {jobs.length === 0 ? (
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          No jobs yet. Create one to get started.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {jobs.map(job => (
            <FolderCard
              key={job.id}
              icon="job"
              title={job.name}
              subtitle={`${job.image_count || 0} images · Created ${new Date(job.created_at).toLocaleDateString()}`}
              status={job.status}
              statusColor={STATUS_COLORS[job.status]}
              onClick={() => navigate(`/jobs/${job.id}`)}
              onRename={() => { setJobToRename(job); setRenameJobName(job.name); }}
              onDelete={() => setJobToDelete(job)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
