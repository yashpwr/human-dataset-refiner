import { Check, Loader2 } from 'lucide-react';

const STEPS = [
  { title: "Initialization & Quality", desc: "Analyzing clarity and resolution" },
  { title: "Deduplication", desc: "Removing exact and near duplicates" },
  { title: "AI Embeddings", desc: "Extracting CLIP and ArcFace tensors" },
  { title: "Identity Clustering", desc: "Grouping unique datasets" },
];

export default function Stepper({ progress = 0, currentStep = '', isComplete = false }) {
  const rawProgress = Math.round(progress);
  const activePhase = isComplete
    ? 4
    : rawProgress < 20 ? 0
    : rawProgress < 40 ? 1
    : Math.max(2, Math.min(3, Math.floor(rawProgress / 33)));

  return (
    <div className="vertical-stack">
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>
        <span>Overall Progress</span>
        <span>{rawProgress}%</span>
      </div>
      <div className="progress-bar-bg" style={{ marginBottom: '1.5rem', marginTop: 0 }}>
        <div className="progress-bar-fill" style={{ width: `${Math.min(100, Math.max(0, rawProgress))}%` }} />
      </div>
      <div className="stepper-container" style={{ marginTop: 0 }}>
        {STEPS.map((step, idx) => {
          const isActive = activePhase === idx;
          const isCompleted = activePhase > idx;
          return (
            <div key={idx} className={`step-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
              <div className="step-indicator">
                {isCompleted
                  ? <Check size={12} strokeWidth={3} />
                  : isActive
                    ? <Loader2 size={12} className="animate-spin" />
                    : <span style={{ fontSize: '10px' }}>{idx + 1}</span>}
              </div>
              <div className="step-content">
                <h5>{step.title}</h5>
                <p>{isActive ? currentStep : step.desc}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
