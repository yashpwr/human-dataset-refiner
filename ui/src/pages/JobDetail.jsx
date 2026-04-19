import { useParams } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import { 
  ArrowLeft, Play, Loader2, Edit2, Trash2, AlertTriangle, 
  ChevronLeft, Settings, Check, X, Zap, Maximize, Users, Repeat,
  Database, Activity, FileText, LayoutDashboard, Terminal, RotateCcw
} from 'lucide-react';
import FolderCard from '../components/FolderCard';
import ImageGrid from '../components/ImageGrid';
import Stepper from '../components/Stepper';
import Modal from '../components/Modal';
import {
  getJob, startJob, listDatasets, assignDataset,
  getJobClusters, renameCluster, deleteCluster, getJobRemoved, 
  dataUrl, updateJobConfig
} from '../api';

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

export default function JobDetail({ navigate }) {
  const { jobId: urlId } = useParams();
  const [job, setJob] = useState(null);
  const [tab, setTab] = useState('overview'); // overview | cluster-view | removed-view
  const [clusters, setClusters] = useState([]);
  const [removed, setRemoved] = useState([]);
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Available datasets
  const [availableDatasets, setAvailableDatasets] = useState([]);
  
  // Modal states
  const [clusterToRename, setClusterToRename] = useState(null);
  const [newClusterName, setNewClusterName] = useState('');
  const [clusterToDelete, setClusterToDelete] = useState(null);
  
  // Config editing state
  const [isConfigEditing, setIsConfigEditing] = useState(false);
  const [editConfig, setEditConfig] = useState(null);
  
  // Dataset change state
  const [isChangingDataset, setIsChangingDataset] = useState(false);

  // Log state
  const [logs, setLogs] = useState([]);
  const lastStepRef = useRef('');
  const logEndRef = useRef(null);

  const jobId = job?.id;
  const jobName = job?.name;

  // Initial fetch for direct URL access
  useEffect(() => {
    if (!urlId) return;
    const fetch = async () => {
      try {
        const data = await getJob(urlId);
        setJob(data);
      } catch (err) {
        console.error("Failed to load job:", err);
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [urlId]);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Poll job status when running
  useEffect(() => {
    if (!jobId) return;
    const fetch = async () => {
      try { 
        const updated = await getJob(jobId);
        setJob(updated);
        
        // Track step changes for logs
        if (updated.status === 'running' && updated.current_step && updated.current_step !== lastStepRef.current) {
           const timestamp = new Date().toLocaleTimeString([], { hour12: false });
           setLogs(prev => [...prev, { time: timestamp, msg: updated.current_step }]);
           lastStepRef.current = updated.current_step;
        }
      } catch (err) {}
    };
    if (job?.status === 'running') {
      const interval = setInterval(fetch, 1000);
      return () => clearInterval(interval);
    }
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
        const updated = await getJob(jobId);
        setJob(updated);
        setIsChangingDataset(false);
    } catch (err) { alert(err.message); }
  };

  const handleStart = async () => {
    if (!job?.dataset_id) {
       alert("Please link a dataset first.");
       return;
    }
    try {
      setLogs([{ time: new Date().toLocaleTimeString([], { hour12: false }), msg: 'Initializing Refiner Pipeline...' }]);
      lastStepRef.current = 'Initializing...';
      setJob(prev => ({ ...prev, status: 'running', progress: 0, current_step: 'Initializing...' }));
      await startJob(jobId);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleUpdateConfig = async (e) => {
    e?.preventDefault();
    try {
      const configToSet = editConfig || DEFAULT_CONFIG;
      await updateJobConfig(jobId, configToSet);
      setJob(await getJob(jobId));
      setIsConfigEditing(false);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleResetToDefaults = async () => {
    if (isConfigEditing) {
      setEditConfig({ ...DEFAULT_CONFIG });
    } else {
      if (window.confirm("Reset all settings to system defaults?")) {
        try {
          await updateJobConfig(jobId, DEFAULT_CONFIG);
          setJob(await getJob(jobId));
        } catch (err) { alert(err.message); }
      }
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
  const isIdle = job?.status === 'idle';

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

  // ── Overview (Level 2 dashboard redesign) ────────────────────────
  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button className="btn btn-secondary" style={{ padding: '0.4rem' }} onClick={() => navigate('jobs')}>
            <ArrowLeft size={18} />
          </button>
          <div>
             <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>{jobName}</h2>
             <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
                <span className="badge" style={{ 
                   color: isRunning ? 'var(--primary-color)' : isComplete ? 'var(--success-color)' : 'var(--text-muted)',
                   borderColor: isRunning ? 'var(--primary-color)' : isComplete ? 'var(--success-color)' : 'var(--surface-border)',
                }}>
                  {job?.status || 'idle'}
                </span>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>ID: {jobId}</span>
             </div>
          </div>
        </div>
      </div>

      <div className="detail-layout">
        {/* Sidebar: Status & Actions */}
        <div className="detail-sidebar">
          
          {/* Dataset Card */}
          <div className="glass-panel" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
              <div style={{ background: 'rgba(59, 130, 246, 0.1)', padding: '0.5rem', borderRadius: '8px', color: 'var(--primary-color)' }}>
                <Database size={20} />
              </div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Input Source</h4>
            </div>
            
            {(!job?.dataset_id || isChangingDataset) ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <select 
                  onChange={(e) => handleAssignDataset(Number(e.target.value))}
                  value={job?.dataset_id || ""}
                  style={{
                    width: '100%', padding: '0.6rem', borderRadius: '6px',
                    border: '1px solid var(--surface-border)', background: 'var(--bg-color)',
                    color: 'var(--text-main)', fontSize: '0.85rem'
                  }}
                >
                  <option value="" disabled>Link a dataset...</option>
                  {availableDatasets.map(ds => (
                    <option key={ds.id} value={ds.id}>{ds.name}</option>
                  ))}
                </select>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', padding: '0.5rem', borderRadius: '4px', flex: 1 }}>
                    Select the source folder to begin refining.
                  </div>
                  {isChangingDataset && (
                    <button className="btn btn-secondary" style={{ padding: '0.4rem 0.6rem', fontSize: '0.7rem' }} onClick={() => setIsChangingDataset(false)}>Cancel</button>
                  )}
                </div>
              </div>
            ) : (
              <div style={{ position: 'relative' }}>
                 <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <div className="badge" style={{ fontSize: '0.65rem', background: 'rgba(16, 185, 129, 0.1)', color: 'var(--success-color)', border: 'none' }}>
                      SOURCE LINKED
                    </div>
                    <button 
                      className="btn btn-secondary" 
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.7rem', opacity: isRunning ? 0.5 : 1 }}
                      onClick={() => setIsChangingDataset(true)}
                      disabled={isRunning}
                    >
                      Change
                    </button>
                 </div>
                 <div style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.25rem' }}>{job?.dataset_name || 'Generic Dataset'}</div>
                 <p style={{ fontSize: '0.8rem' }}>{job?.image_count || 0} images linked</p>
              </div>
            )}
          </div>

          {/* Activity/Status Card */}
          <div className="glass-panel" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '0.5rem', borderRadius: '8px', color: 'var(--success-color)' }}>
                <Activity size={20} />
              </div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Pipeline Action</h4>
            </div>

            <button className="btn" onClick={handleStart} disabled={isRunning || !job?.dataset_id}
              style={{ width: '100%', padding: '0.75rem', opacity: (isRunning || !job?.dataset_id) ? 0.5 : 1 }}>
              {isRunning ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
              {isRunning ? 'Running...' : 'Execute Pipeline'}
            </button>
            
            {isRunning && (
              <div style={{ marginTop: '1.25rem' }}>
                <Stepper progress={job.progress || 0} currentStep={job.current_step || ''} />
              </div>
            )}

            {job?.status === 'failed' && (
              <div style={{ marginTop: '1rem', padding: '0.75rem', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--error-color)', fontSize: '0.8rem', display: 'flex', gap: '0.5rem' }}>
                <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                <span>{job.error}</span>
              </div>
            )}
          </div>
        </div>

        {/* Main: Configuration Dashboard */}
        <div className="detail-main">
          
          {/* Configuration Panel */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
               <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{ background: 'rgba(245, 158, 11, 0.1)', padding: '0.5rem', borderRadius: '8px', color: 'var(--warning-color)' }}>
                    <Settings size={20} />
                  </div>
                  <h4 style={{ fontSize: '1rem', fontWeight: 600 }}>Algorithm Thresholds</h4>
               </div>
               
               {job && (
                 <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {!isConfigEditing ? (
                      <button 
                        className="btn btn-secondary" 
                        style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', opacity: isRunning ? 0.5 : 1 }} 
                        onClick={() => { setEditConfig({ ...DEFAULT_CONFIG, ...(job?.config || {}) }); setIsConfigEditing(true); }}
                        disabled={isRunning}
                      >
                        <Edit2 size={14} /> Tune Logic
                      </button>
                    ) : (
                      <>
                        <button 
                          className="btn btn-secondary" 
                          style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', borderStyle: 'dashed', opacity: isRunning ? 0.5 : 1 }} 
                          onClick={handleResetToDefaults} 
                          title="Reset all to system defaults"
                          disabled={isRunning}
                        >
                          <RotateCcw size={14} /> Reset
                        </button>
                        <button className="btn btn-secondary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }} onClick={() => setIsConfigEditing(false)}>Cancel</button>
                        <button 
                          className="btn" 
                          style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', opacity: isRunning ? 0.5 : 1 }} 
                          onClick={handleUpdateConfig}
                          disabled={isRunning}
                        >
                           <Check size={14} /> Apply
                        </button>
                      </>
                    )}
                 </div>
               )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
               <div>
                  <div className="config-section-title"><Zap size={14} /> Advanced Filtering</div>
                  <div className="compact-config-grid">
                      <div className="config-card">
                        <span className="config-label">Blur Sens.</span>
                        {isConfigEditing ? (
                          <input type="number" step="0.5" value={editConfig?.blur_threshold} onChange={e => {
                            const val = parseFloat(e.target.value);
                            setEditConfig({...editConfig, blur_threshold: isNaN(val) ? 0 : val});
                          }} className="config-input" />
                        ) : (
                          <span className="mono" style={{ fontSize: '1rem', fontWeight: 600 }}>{job?.config?.blur_threshold ?? 35}</span>
                        )}
                        <p className="config-desc">Laplacian variance threshold.</p>
                      </div>
                      <div className="config-card">
                        <span className="config-label">Min Size</span>
                        {isConfigEditing ? (
                          <input type="number" value={editConfig?.min_resolution} onChange={e => {
                            const val = parseInt(e.target.value);
                            setEditConfig({...editConfig, min_resolution: isNaN(val) ? 0 : val});
                          }} className="config-input" />
                        ) : (
                          <span className="mono" style={{ fontSize: '1rem', fontWeight: 600 }}>{job?.config?.min_resolution ?? 64}px</span>
                        )}
                        <p className="config-desc">Reject tiny low-res images.</p>
                      </div>
                      <div className="config-card">
                        <span className="config-label">Face Size</span>
                        {isConfigEditing ? (
                          <input type="number" value={editConfig?.min_face_size} onChange={e => {
                            const val = parseInt(e.target.value);
                            setEditConfig({...editConfig, min_face_size: isNaN(val) ? 0 : val});
                          }} className="config-input" />
                        ) : (
                          <span className="mono" style={{ fontSize: '1rem', fontWeight: 600 }}>{job?.config?.min_face_size ?? 50}px</span>
                        )}
                        <p className="config-desc">Ignore background faces.</p>
                      </div>
                  </div>
               </div>

               <div>
                  <div className="config-section-title"><Users size={14} /> Clustering Intelligence</div>
                  <div className="compact-config-grid">
                      <div className="config-card">
                        <span className="config-label">Clustering Strictness</span>
                        {isConfigEditing ? (
                          <input type="number" step="0.05" value={editConfig?.face_distance_threshold} onChange={e => {
                            const val = parseFloat(e.target.value);
                            setEditConfig({...editConfig, face_distance_threshold: isNaN(val) ? 0 : val});
                          }} className="config-input" />
                        ) : (
                          <span className="mono" style={{ fontSize: '1rem', fontWeight: 600 }}>{job?.config?.face_distance_threshold ?? 0.55}</span>
                        )}
                        <p className="config-desc">Identity grouping threshold.</p>
                      </div>
                      <div className="config-card" style={{ gridColumn: 'span 2' }}>
                        <span className="config-label">Enabled Pipeline Stages</span>
                        <div style={{ display: 'flex', gap: '2rem', marginTop: '0.4rem' }}>
                            <label style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', cursor: isConfigEditing ? 'pointer' : 'default' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                                <input type="checkbox" disabled={!isConfigEditing} checked={isConfigEditing ? editConfig?.enable_quality_check : (job?.config?.enable_quality_check ?? true)} onChange={e => setEditConfig({...editConfig, enable_quality_check: e.target.checked})} />
                                Quality Check
                              </div>
                              <p className="config-desc" style={{ marginTop: 0 }}>Filter blurry, low-res, or corrupted images.</p>
                            </label>
                            <label style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', cursor: isConfigEditing ? 'pointer' : 'default' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                                <input type="checkbox" disabled={!isConfigEditing} checked={isConfigEditing ? editConfig?.enable_duplicate_check : (job?.config?.enable_duplicate_check ?? true)} onChange={e => setEditConfig({...editConfig, enable_duplicate_check: e.target.checked})} />
                                Duplicate Check
                              </div>
                              <p className="config-desc" style={{ marginTop: 0 }}>Remove visually identical images using pHash.</p>
                            </label>
                        </div>
                      </div>
                  </div>
               </div>
            </div>
          </div>

          {/* Log Console (Show when running or failed) */}
          {(isRunning || job?.status === 'failed') && (
             <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.2rem' }}>
                    <div style={{ background: 'rgba(255, 255, 255, 0.05)', padding: '0.4rem', borderRadius: '6px', color: 'var(--text-main)' }}>
                      <Terminal size={18} />
                    </div>
                    <h4 style={{ fontSize: '1rem', fontWeight: 600 }}>Server Session Logs</h4>
                </div>
                <div className="log-console">
                   {logs.map((log, i) => (
                     <div key={i} className="log-line">
                        <span className="log-timestamp">[{log.time}]</span>
                        <span className="log-level">[INFO]</span>
                        <span className={`log-msg ${i === logs.length - 1 ? 'highlight' : ''}`}>{log.msg}</span>
                     </div>
                   ))}
                   {isRunning && (
                      <div className="log-line">
                        <span className="log-timestamp">[{new Date().toLocaleTimeString([], { hour12: false })}]</span>
                        <span className="log-level" style={{ color: 'var(--text-muted)' }}>[WAIT]</span>
                        <span className="log-msg" style={{ opacity: 0.8 }}>Awaiting next cycle...</span>
                      </div>
                   )}
                   <div ref={logEndRef} />
                </div>
             </div>
          )}

          {/* Results Grid (If complete) */}
          {isComplete && (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                  <div style={{ background: 'rgba(59, 130, 246, 0.1)', padding: '0.4rem', borderRadius: '6px', color: 'var(--primary-color)' }}>
                    <LayoutDashboard size={18} />
                  </div>
                  <h4 style={{ fontSize: '1rem', fontWeight: 600 }}>Refined Output</h4>
              </div>
              
              <div className="cluster-grid">
                {/* Regular Clusters */}
                {clusters.map(c => {
                  const folderName = c.cluster_name || `cluster_${String(c.cluster_id).padStart(3, '0')}`;
                  const thumbnail = c.member_filenames?.[0];
                  return (
                    <div key={c.cluster_id} className="cluster-card-premium" onClick={() => { setSelectedCluster(c); setTab('cluster-view'); }}>
                       <div className="cluster-badge-abs">
                          <span className="badge" style={{ fontSize: '0.6rem', padding: '0.15rem 0.5rem' }}>
                             {c.cluster_type.toUpperCase()}
                          </span>
                       </div>
                       
                       <div className="cluster-thumbnail-container">
                          {thumbnail ? (
                            <img 
                              src={dataUrl(`jobs/${jobName}/grouped/${folderName}/${thumbnail}`)} 
                              alt={folderName} 
                              className="cluster-thumbnail"
                            />
                          ) : (
                            <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(255,255,255,0.05)' }}>
                               <Users size={32} style={{ opacity: 0.2 }} />
                            </div>
                          )}
                          <div className="cluster-info-overlay">
                             <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', width: '100%' }}>
                                <div>
                                   <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#fff' }}>{folderName}</div>
                                   <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.7)' }}>{c.member_count} images</div>
                                </div>
                                <button className="btn-icon" onClick={e => { e.stopPropagation(); setClusterToDelete(c); }}>
                                   <Trash2 size={14} color="#f87171" />
                                </button>
                             </div>
                          </div>
                       </div>
                    </div>
                  );
                })}

                {/* Removed Items (Cleanup Card) */}
                {removed && removed.length > 0 && (
                  <div className="cluster-card-premium cleanup" onClick={() => setTab('removed-view')}>
                     <div className="cluster-badge-abs">
                        <span className="badge" style={{ fontSize: '0.6rem', padding: '0.15rem 0.5rem', background: 'rgba(245, 158, 11, 0.1)', color: 'var(--warning-color)', borderStyle: 'dotted' }}>
                           CLEANUP
                        </span>
                     </div>
                     
                     <div className="cluster-thumbnail-container">
                        {removed[0]?.filename ? (
                          <img 
                            src={dataUrl(`jobs/${jobName}/removed/${removed[0].filename}`)} 
                            alt="Cleanup" 
                            className="cluster-thumbnail"
                          />
                        ) : (
                          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(245, 158, 11, 0.05)' }}>
                             <Trash2 size={40} style={{ opacity: 0.2, color: 'var(--warning-color)' }} />
                          </div>
                        )}
                        <div className="cluster-info-overlay" style={{ background: 'linear-gradient(to top, rgba(0, 0, 0, 0.9) 0%, rgba(245, 158, 11, 0.4) 40%, transparent 100%)' }}>
                           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', width: '100%' }}>
                              <div>
                                 <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#fff' }}>Removed Images</div>
                                 <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.9)' }}>{removed.length} low-quality/redundant items</div>
                              </div>
                              <div style={{ background: 'var(--warning-color)', padding: '0.4rem', borderRadius: '50%', color: '#000', boxShadow: '0 2px 4px rgba(0,0,0,0.3)' }}>
                                 <Trash2 size={14} />
                              </div>
                           </div>
                        </div>
                     </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {!isComplete && !isRunning && job?.status !== 'failed' && (
            <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)', borderStyle: 'dashed' }}>
              <Activity size={32} style={{ opacity: 0.2, marginBottom: '1rem' }} />
              <p>Execute the pipeline to see identity clusters and quality results.</p>
            </div>
          )}

        </div>
      </div>

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
        <p style={{ marginBottom: '1.5rem' }}>Are you sure you want to delete this cluster? All its images will be permanently removed.</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={() => setClusterToDelete(null)}>Cancel</button>
          <button className="btn btn-danger" onClick={handleDeleteCluster}>Delete Permanently</button>
        </div>
      </Modal>

    </div>
  );
}
