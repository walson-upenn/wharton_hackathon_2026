export default function AgentModal({ open, onClose }) {
  if (!open) return null;

  return (
    <div className="agent-modal__backdrop" onClick={onClose}>
      <div
        className="agent-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="AI review assistant"
      >
        <div className="agent-modal__header">
          <div className="agent-avatar">AI</div>
          <div>
            <div className="agent-title">Finish by talking</div>
            <div className="agent-subtitle">Expedia AI assistant</div>
          </div>
          <button className="agent-close" onClick={onClose} type="button">
            ×
          </button>
        </div>

        <div className="agent-message">
          You can just talk naturally. I’ll guide the review and organize your
          feedback for you.
        </div>

        <div className="agent-typing">
          <span />
          <span />
          <span />
        </div>

        <div className="agent-actions">
          <button type="button" className="primary-button">
            Start voice review
          </button>
          <button type="button" className="secondary-button">
            Type with assistant
          </button>
        </div>
      </div>
    </div>
  );
}