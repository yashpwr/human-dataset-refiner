import { useState, useEffect } from 'react';
import { BarChart2, Settings } from 'lucide-react';
import { listJobs, getJob, getJobClusters, getJobRemoved } from '../api';

export default function Report() {
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [jobData, setJobData] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [removed, setRemoved] = useState([]);

  useEffect(() => {
    listJobs().then(data => {
      setJobs(data);
      const completed = data.find(j => j.status === 'completed');
      if (completed) setSelectedJobId(completed.id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedJobId) return;
    getJob(selectedJobId).then(setJobData).catch(() => {});
    getJobClusters(selectedJobId).then(setClusters).catch(() => setClusters([]));
    getJobRemoved(selectedJobId).then(setRemoved).catch(() => setRemoved([]));
  }, [selectedJobId]);

  const accepted = jobData ? (jobData.total_images || 0) - removed.length : 0;

  const METRICS = [
    { label: 'Total Images', value: jobData?.total_images || 0, color: 'var(--text-main)', tip: 'Total images processed by the pipeline.' },
    { label: 'Accepted', value: accepted, color: 'var(--success-color)', tip: 'Images that passed quality checks and were clustered.' },
    { label: 'Removed', value: removed.length, color: 'var(--warning-color)', tip: 'Images removed due to quality, duplicates, or no cluster match.' },
    { label: 'Clusters', value: clusters.length, color: 'var(--primary-color)', tip: 'Number of identity groups formed.' },
  ];

  return (
    <div className="animate-fade-in">
      <div className="view-header">
        <h2>Pipeline Report</h2>
        <p>Telemetry and processing breakdown.</p>
      </div>

      {jobs.length > 1 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <select
            value={selectedJobId || ''}
            onChange={e => setSelectedJobId(Number(e.target.value))}
            style={{
              padding: '0.5rem 1rem', borderRadius: 'var(--radius)',
              background: 'var(--surface-color)', color: 'var(--text-main)',
              border: '1px solid var(--surface-border)', fontSize: '0.9rem',
            }}
          >
            {jobs.filter(j => j.status === 'completed').map(j => (
              <option key={j.id} value={j.id}>{j.name}</option>
            ))}
          </select>
        </div>
      )}

      {!jobData || jobData.status !== 'completed' ? (
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          No completed report available. Run a pipeline first.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BarChart2 size={18} color="var(--primary-color)" /> Summary — {jobData.name}
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
              {METRICS.map(m => (
                <div key={m.label} title={m.tip} style={{
                  padding: '1rem', background: 'var(--surface-color-hover)',
                  borderRadius: 'var(--radius)', cursor: 'help',
                }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>{m.label}</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600, color: m.color }}>{m.value}</div>
                </div>
              ))}
            </div>
          </div>

          {removed.length > 0 && (
            <div className="glass-panel" style={{ padding: '1.5rem' }}>
              <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Settings size={18} color="var(--primary-color)" /> Removal Breakdown
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
                {Object.entries(
                  removed.reduce((acc, r) => {
                    const key = (r.reason || 'unknown').replace(/_/g, ' ').toUpperCase();
                    acc[key] = (acc[key] || 0) + 1;
                    return acc;
                  }, {})
                ).map(([reason, count]) => (
                  <div key={reason} style={{
                    padding: '0.75rem', borderLeft: '3px solid var(--warning-color)',
                    background: 'var(--surface-color-hover)', borderRadius: '4px',
                  }}>
                    <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{reason}</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--warning-color)', marginTop: '0.25rem' }}>{count}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
