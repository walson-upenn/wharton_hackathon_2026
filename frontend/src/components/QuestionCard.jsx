export default function QuestionCard({
  question,
  value,
  onChange,
  currentIndex,
  total,
  onNext,
  onPreviousQuestion,
  onBack,
  animateIn,
}) {
  if (question.type !== "text") return null;

  const isLast = currentIndex === total - 1;
  const charCount = value.length;

  return (
    <section
      className={`review-card review-card--question ${
        animateIn ? "is-visible" : "is-exiting"
      }`}
    >
      <div className="question-topline">
        <span className="section-kicker">
          Question {currentIndex + 1} of {total}
        </span>
      </div>

      <h2 className="section-title section-title--compact">{question.label}</h2>

      {question.askReason && (
        <p className="question-reason">{question.askReason}</p>
      )}

      <div className="textarea-wrap">
        <textarea
          className="details-textarea"
          placeholder={question.placeholder || "Type your answer..."}
          value={value}
          maxLength={500}
          onChange={(e) => onChange(question.id, e.target.value)}
        />
        <div className={`char-count ${charCount > 450 ? "char-count--warn" : ""}`}>
          {charCount} / 500
        </div>
      </div>

      <div className="question-actions">
        {currentIndex > 0 ? (
          <button
            type="button"
            className="neutral-button"
            onClick={onPreviousQuestion}
          >
            Previous
          </button>
        ) : (
          <button
            type="button"
            className="neutral-button"
            onClick={onBack}
          >
            ← Return to previous step
          </button>
        )}

        {!isLast && (
          <button
            type="button"
            className="neutral-button neutral-button--strong"
            onClick={onNext}
          >
            Next
          </button>
        )}
      </div>
    </section>
  );
}