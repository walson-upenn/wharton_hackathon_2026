export default function QuestionCard({
  question,
  value,
  onChange,
  currentIndex,
  total,
  onNext,
  onPreviousQuestion,
  animateIn,
}) {
  if (question.type !== "text") {
    return null;
  }

  const isLast = currentIndex === total - 1;
  const hasInput = value.trim().length > 0;

  return (
    <section
      className={`review-card review-card--question ${
        animateIn ? "is-visible" : "is-exiting"
      }`}
    >
      <div className="question-topline">
        <span className="section-kicker">Question {currentIndex + 1} of {total}</span>
      </div>

      <h2 className="section-title section-title--compact">{question.label}</h2>

      <textarea
        className="details-textarea"
        placeholder={question.placeholder || "Type your answer..."}
        value={value}
        onChange={(e) => onChange(question.id, e.target.value)}
      />

      <div className="question-actions">
        {currentIndex > 0 && (
          <button
            type="button"
            className="neutral-button"
            onClick={onPreviousQuestion}
          >
            Previous question
          </button>
        )}

        <button
          type="button"
          className={`neutral-button ${
            hasInput ? "question-cta-button--yellow" : "neutral-button--strong"
          }`}
          onClick={onNext}
        >
          {isLast ? "Done" : "Next"}
        </button>
      </div>
    </section>
  );
}

