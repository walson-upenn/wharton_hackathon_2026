export default function ProgressBar({ step, stepProgress }) {
  const pct = Math.round(((step - 1) * 50) + stepProgress * 50);
  return (
    <div className="progress-wrap">
      <div className="progress-meta">
        <span className="progress-label">Step {step} of 2</span>
        <span className="progress-pct">{pct}%</span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}