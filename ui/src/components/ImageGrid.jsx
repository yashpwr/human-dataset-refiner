import { Trash2 } from 'lucide-react';

/**
 * Reusable image grid — used for input images, cluster images, removed images.
 *
 * Props:
 *   images     - string[] of filenames
 *   getUrl     - (filename) => image URL
 *   onDelete   - optional (filename) => void — shows delete icon if provided
 *   overlay    - optional (filename) => string — overlay badge text
 *   compact    - boolean — if true, renders smaller cluster-style cells
 */
export default function ImageGrid({ images = [], getUrl, onDelete, overlay, compact = false }) {
  if (compact) {
    return (
      <div className="cluster-grid">
        {images.map(img => (
          <div className="cluster-img-wrap" key={img} style={{ position: 'relative' }}>
            <img src={getUrl(img)} alt={img} loading="lazy" />
            {overlay && overlay(img) && (
              <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                background: 'rgba(0,0,0,0.85)', color: 'var(--warning-color)',
                padding: '0.35rem', fontSize: '0.65rem', textAlign: 'center', fontWeight: 'bold',
              }}>
                {overlay(img)}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="dataset-grid">
      {images.map(img => (
        <div className="image-card" key={img}>
          <img src={getUrl(img)} alt={img} loading="lazy" />
          <div className="image-card-footer">
            <span className="mono" style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{img}</span>
            {onDelete && (
              <button className="btn-icon" onClick={() => onDelete(img)} title="Remove">
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
