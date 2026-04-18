import { useState, useEffect } from 'react';
import { ArrowLeft, Play, Loader2, Edit2, Trash2, AlertTriangle, ChevronLeft } from 'lucide-react';
import FolderCard from '../components/FolderCard';
import ImageGrid from '../components/ImageGrid';
import Stepper from '../components/Stepper';
import Modal from '../components/Modal';
import {
  getJob, startJob, listDatasets, assignDataset,
  getJobClusters, renameCluster, deleteCluster, getJobRemoved, dataUrl,
} from '../api';

export default function JobDetail({ job: initialJob, navigate }) {
  const [job, setJob] = useState(initialJob);
  const [tab, setTab] = useState('overview'); // overview | cluster-view | removed-view
  const [clusters, setClusters] = useState([]);
  const [removed, setRemoved] = useState([]);
  const [selectedCluster, setSelectedCluster] = useState(null);
  
  // Available datasets
  const [availableDatasets, setAvailableDatasets] = useState([]);
  
  // Modal states
  const [clusterToRename, setClusterToRename] = useState(null);
  const [newClusterName, setNewClusterName] = useState('');
  const [clusterToDelete, setClusterToDelete] = useState(null);

  const jobId = job?.id;
  const jobName = job?.name;

  // Poll job status when running
  useEffect(() => {
    if (!jobId) return;
    const fetch = async () => {
      try { setJob(await getJob(jobId)); } catch (err) {}
    };
    fetch();
    const interval = setInterval(fetch, job?.status === 'running' ? 500 : 3000);
    return () => clearInterval(interval);
  }, [jobId, job?.status]);

  // Fetch data based on tab
  useEffect(() => {
    if (!jobId) return;
    if (tab === 'overview') {
      getJobClusters(jobId).then(setClusters).catch(() => setClusters([]));
      getJobRemoved(jobId).then(setRemoved).catch(() => setRemoved([]));
      listDatasets().then(setAvailableDatasets).catch(() => {});
    }
  }, [jobId, tab, job?.status]);

  const handleAssignDataset = async (datasetId) => {
    if (!datasetId) return;
    try {
       await assignDataset(jobId, datasetId);
       setJob(await getJob(jobId)); // refresh job to show assigned dataset
    } catch (err) { alert(err.message); }
  };

  const handleStart = async () => {
    if (!job?.dataset_id) {
       alert("Please link a dataset first.");
       return;
    }
    try {
      setJob(prev => ({ ...prev, status: 'running', progress: 0, current_step: 'Initializing...' }));
      await startJob(jobId);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleRenameCluster = async (e) => {
    e.preventDefault();
    if (!newClusterName.trim() || !clusterToRename) return;
    try {
      await renameCluster(jobId, clusterToRename.cluster_id, newClusterName.trim());
      setClusters(await getJobClusters(jobId));
      setClusterToRename(null);
      setNewClusterName('');
      if (selectedCluster?.cluster_id === clusterToRename.cluster_id) {
         setSelectedCluster({ ...selectedCluster, cluster_name: newClusterName.trim() });
      }
    } catch (err) { alert(err.message); }
  };

  const handleDeleteCluster = async () => {
    if (!clusterToDelete) return;
    try {
      await deleteCluster(jobId, clusterToDelete.cluster_id);
      setClusters(await getJobClusters(jobId));
      if (selectedCluster?.cluster_id === clusterToDelete.cluster_id) {
         setSelectedCluster(null);
         setTab('overview');
      }
      setClusterToDelete(null);
    } catch (err) { alert(err.message); }
  };

  const isRunning = job?.status === 'running';
  const isComplete = job?.status === 'completed';

  // ── Cluster detail sub-view ───────────────────────────────────────
  if (tab === 'cluster-view' && selectedCluster) {
    const c = selectedCluster;
    const folderName = c.cluster_name || `cluster_${String(c.cluster_id).padStart(3, '0')}`;
    return (
      <div className="animate-fade-in">
        <button className="btn btn-secondary" onClick={() => { setTab('overview'); setSelectedCluster(null); }} style={{ marginBottom: '1.5rem' }}>
          <ChevronLeft size={16} /> Back to {jobName}
        </button>
        <div className="view-header">
          <h2>{folderName}</h2>
          <p>{c.member_count} images in this cluster</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
          <button className="btn btn-secondary" onClick={() => { setClusterToRename(c); setNewClusterName(folderName); }}>
            <Edit2 size={14} /> Rename
          </button>
          <button className="btn btn-danger" onClick={() => setClusterToDelete(c)}>
            <Trash2 size={14} /> Delete
          </button>
        </div>
        <ImageGrid
          images={c.member_filenames || []}
          getUrl={(fn) => dataUrl(`jobs/${jobName}/grouped/${folderName}/${fn}`)}
        />
      </div>
    );
  }

  // ── Removed detail sub-view ───────────────────────────────────────
  if (tab === 'removed-view') {
    return (
      <div className="animate-fade-in">
        <button className="btn btn-secondary" onClick={() => setTab('overview')} style={{ marginBottom: '1.5rem' }}>
          <ChevronLeft size={16} /> Back to {jobName}
        </button>
        <div className="view-header">
          <h2>Removed Images</h2>
          <p>{removed.length} images were removed during processing</p>
        </div>
        <ImageGrid
          images={removed.map(r => r.filename)}
          getUrl={(fn) => {
            const rec = removed.find(r => r.filename === fn);
            const reason = rec?.reason || 'unknown';
            return dataUrl(`jobs/${jobName}/removed/${reason}/${fn}`);
          }}
          compact
          overlay={(fn) => {
            const rec = removed.find(r => r.filename === fn);
            return rec?.reason ? rec.reason.replace(/_/g, ' ').toUpperCase() : 'REMOVED';
          }}
        />
      </div>
    );
  }

  // ── Overview (Level 2: cluster folders + removed folder) ──────────
  return (
    <div className="animate-fade-in">
      <button className="btn btn-secondary" onClick={() => navigate('jobs')} style={{ marginBottom: '1.5rem' }}>
        <ArrowLeft size={16} /> All Jobs
      </button>

      <div className="view-header">
        <h2>{jobName}</h2>
        <p>
          Status: <strong style={{ color: isRunning ? 'var(--primary-color)' : isComplete ? 'var(--success-color)' : 'var(--text-muted)' }}>
            {job?.status?.toUpperCase() || 'IDLE'}
          </strong>
        </p>
      </div>

      {/* Dataset Selection */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <h4 style={{ marginBottom: '0.75rem', fontSize: '0.95rem' }}>Input Dataset</h4>
        {!job?.dataset_id && !isRunning && !isComplete ? (
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <select
              defaultValue=""
              onChange={e => handleAssignDataset(Number(e.target.value))}
              style={{
                flex: 1, padding: '0.75rem', borderRadius: '4px',
                border: '1px solid var(--surface-border)', background: 'var(--bg-color)',
                color: 'var(--text-main)'
              }}
            >
              <option value="" disabled>Select a dataset to link...</option>
              {availableDatasets.map(ds => (
                <option key={ds.id} value={ds.id}>{ds.name} ({ds.image_count} images)</option>
              ))}
            </select>
            <button className="btn btn-secondary" onClick={() => navigate('datasets')}>Manage Datasets</button>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
             <span style={{ fontSize: '1rem', fontWeight: 500 }}>{job?.dataset_name || 'Deleted Dataset'}</span>
             <span style={{ color: 'var(--text-muted)' }}>· {job?.image_count || 0} input images</span>
          </div>
        )}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
        <button className="btn" onClick={handleStart} disabled={isRunning || !job?.dataset_id}
          style={{ opacity: (isRunning || !job?.dataset_id) ? 0.5 : 1, cursor: (isRunning || !job?.dataset_id) ? 'not-allowed' : 'pointer' }}>
          {isRunning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {isRunning ? 'Processing...' : 'Start Pipeline'}
        </button>
      </div>

      {/* Running progress */}
      {isRunning && (
        <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
          <Stepper progress={job.progress || 0} currentStep={job.current_step || ''} />
        </div>
      )}

      {job?.status === 'failed' && (
        <div className="glass-panel" style={{ padding: '1rem', marginBottom: '1.5rem', background: 'rgba(239,68,68,0.1)', color: 'var(--error-color)' }}>
          <AlertTriangle size={16} /> Error: {job.error}
        </div>
      )}

      {/* Cluster & Removed Folders (Level 2) */}
      {isComplete && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {clusters.map(c => {
            const folderName = c.cluster_name || `cluster_${String(c.cluster_id).padStart(3, '0')}`;
            return (
              <FolderCard
                key={c.cluster_id}
                icon="cluster"
                title={folderName}
                subtitle={`${c.member_count} images`}
                status={c.cluster_type}
                statusColor="var(--primary-color)"
                onClick={() => { setSelectedCluster(c); setTab('cluster-view'); }}
                onDelete={() => setClusterToDelete(c)}
              />
            );
          })}
          {removed.length > 0 && (
            <FolderCard
              icon="removed"
              title="Removed"
              subtitle={`${removed.length} images removed`}
              status="noise"
              statusColor="var(--warning-color)"
              onClick={() => setTab('removed-view')}
            />
          )}
          {clusters.length === 0 && removed.length === 0 && (
            <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              Pipeline completed but no clusters found.
            </div>
          )}
        </div>
      )}

      {!isComplete && !isRunning && job?.status !== 'failed' && (
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          Upload images and start the pipeline to see results here.
        </div>
      )}

      {/* Modals */}
      <Modal isOpen={!!clusterToRename} onClose={() => setClusterToRename(null)} title="Rename Cluster">
        <form onSubmit={handleRenameCluster}>
          <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>New Folder Name</label>
          <input 
            type="text" autoFocus value={newClusterName} onChange={e => setNewClusterName(e.target.value)}
            style={{ width: '100%', padding: '0.75rem', borderRadius: '4px', border: '1px solid var(--surface-border)', background: 'var(--bg-color)', color: 'var(--text-main)', marginBottom: '1.5rem', fontSize: '1rem' }} 
          />
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-secondary" onClick={() => setClusterToRename(null)}>Cancel</button>
            <button type="submit" className="btn" disabled={!newClusterName.trim()}>Rename</button>
          </div>
        </form>
      </Modal>

      <Modal isOpen={!!clusterToDelete} onClose={() => setClusterToDelete(null)} title="Delete Cluster">
        <p style={{ marginBottom: '1.5rem' }}>Are you sure you want to delete this cluster? The folder and all its images will be permanently removed.</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={() => setClusterToDelete(null)}>Cancel</button>
          <button className="btn btn-danger" onClick={handleDeleteCluster}>Delete Permanently</button>
        </div>
      </Modal>

    </div>
  );
}
