import { Folder, Briefcase, Trash2, Edit2, ChevronRight } from 'lucide-react';

/**
 * Reusable folder card — used for job cards and cluster cards.
 *
 * Props:
 *   title       - display name
 *   subtitle    - secondary info (e.g. "12 images", "completed")
 *   onClick     - click handler to drill in
 *   onDelete    - optional delete handler (shows trash icon)
 *   onRename    - optional rename handler (shows edit icon)
 *   icon        - 'job' | 'cluster' | 'removed'
 *   status      - optional status badge text
 *   statusColor - optional badge color
 */
export default function FolderCard({ title, subtitle, onClick, onDelete, onRename, icon = 'job', status, statusColor }) {
  const IconComp = icon === 'job' ? Briefcase : Folder;
  const iconColor = icon === 'removed' ? 'var(--warning-color)' : 'var(--primary-color)';

  return (
    <div
      className="glass-panel folder-card"
      onClick={onClick}
      style={{ cursor: 'pointer' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flex: 1 }}>
        <div style={{
          width: '42px', height: '42px', borderRadius: 'var(--radius)',
          background: icon === 'removed' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(59, 130, 246, 0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <IconComp size={20} color={iconColor} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h4 style={{ fontSize: '0.95rem', marginBottom: '0.15rem' }}>{title}</h4>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{subtitle}</p>
        </div>
        {status && (
          <span className="badge" style={statusColor ? {
            background: `${statusColor}20`, color: statusColor, borderColor: `${statusColor}40`,
          } : {}}>
            {status}
          </span>
        )}
        {onRename && (
          <button className="btn-icon" onClick={e => { e.stopPropagation(); onRename(); }} title="Rename">
            <Edit2 size={16} color="var(--text-muted)" />
          </button>
        )}
        {onDelete && (
          <button className="btn-icon" onClick={e => { e.stopPropagation(); onDelete(); }} title="Delete">
            <Trash2 size={16} color="var(--error-color)" />
          </button>
        )}
        <ChevronRight size={16} color="var(--text-muted)" />
      </div>
    </div>
  );
}
