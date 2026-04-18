import { AlertTriangle } from 'lucide-react';

export default function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="glass-panel" style={{
      padding: '1rem', marginBottom: '1rem',
      background: 'rgba(239, 68, 68, 0.1)',
      color: 'var(--error-color)',
      display: 'flex', gap: '0.5rem', alignItems: 'center',
    }}>
      <AlertTriangle size={18} /> {message}
    </div>
  );
}
