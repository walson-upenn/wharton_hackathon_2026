import { useState } from "react";
import "./App.css";
import ReviewHeader from "./components/ReviewHeader";
import PropertyCard from "./components/PropertyCard";
import OverallRating from "./components/OverallRating";
import QuestionCard from "./components/QuestionCard";
import mockReviewSession from "./data/mockReviewSession";

export default function App() {
  const [session] = useState(mockReviewSession);

  const [viewMode, setViewMode] = useState("agent");
  // "agent" | "form_setup" | "form_questions"

  const [stageAnimateIn, setStageAnimateIn] = useState(true);
  const [questionAnimateIn, setQuestionAnimateIn] = useState(true);

  const [travelType, setTravelType] = useState("");
  const [stayUsage, setStayUsage] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);

  const textQuestions = session.questions.filter((q) => q.type === "text");

  const [answers, setAnswers] = useState({
    q_overall: 0,
    q_1: "",
    q_2: "",
  });

  const setupComplete =
    answers.q_overall > 0 &&
    travelType.trim().length > 0 &&
    stayUsage.length > 0;

  const currentQuestion = textQuestions[currentQuestionIndex];

  const handleQuestionChange = (questionId, value) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  const handleToggleStayUsage = (option) => {
    setStayUsage((prev) =>
      prev.includes(option)
        ? prev.filter((item) => item !== option)
        : [...prev, option]
    );
  };

  const switchStage = (nextStage) => {
    setStageAnimateIn(false);

    window.setTimeout(() => {
      setViewMode(nextStage);
      setStageAnimateIn(true);
    }, 280);
  };

  const triggerQuestionTransition = (nextIndex) => {
    setQuestionAnimateIn(false);

    window.setTimeout(() => {
      setCurrentQuestionIndex(nextIndex);
      setQuestionAnimateIn(true);
    }, 280);
  };

  const handleNextQuestion = () => {
    if (currentQuestionIndex < textQuestions.length - 1) {
      triggerQuestionTransition(currentQuestionIndex + 1);
    }
  };

  const handleSkipQuestion = () => {
    if (currentQuestionIndex < textQuestions.length - 1) {
      triggerQuestionTransition(currentQuestionIndex + 1);
    }
  };

  const handleSubmit = () => {
    if (!answers.q_overall) {
      alert("Please give an overall rating first.");
      return;
    }

    const payload = {
      reviewId: session.reviewId,
      travelType,
      stayUsage,
      answers,
    };

    console.log("submit payload:", payload);
    alert("Review payload logged in console. Next step: connect POST API.");
  };

  return (
    <div className="page-shell">
      <ReviewHeader />

      <main className="page-content">
        <div className="top-meta-line">
          <span className="top-meta-line__muted">Write a review</span>
        </div>

        <PropertyCard property={session.property} />

        {viewMode === "agent" && (
          <section
            className={`agent-embed-card ${
              stageAnimateIn ? "is-visible" : "is-exiting"
            }`}
          >
            <div className="agent-embed-card__header">
              <div>
                <div className="agent-embed-card__title">Talk to Expedia AI</div>
                <div className="agent-embed-card__subtitle">
                  Complete your review in a natural conversation.
                </div>
                <div className="agent-embed-card__meta">
                  Most reviews take less than a minute.
                </div>
              </div>

              <button
                type="button"
                className="agent-close-inline"
                onClick={() => switchStage("form_setup")}
                aria-label="Use the form instead"
                title="Use the form instead"
              >
                ×
              </button>
            </div>

            <div className="agent-live-panel">
              <div className="agent-live-panel__left">
                <div className="agent-live-status">
                  <span className="agent-live-status__dot" />
                  Live voice assistant
                </div>

                <div className="agent-live-message">
                  Hi, I can help you finish this review by voice. Just start
                  talking.
                </div>

                <div className="agent-live-actions">
                  <button
                    type="button"
                    className="neutral-button neutral-button--strong"
                  >
                    Start talking
                  </button>

                  <button
                    type="button"
                    className="text-link-button"
                    onClick={() => switchStage("form_setup")}
                  >
                    Use the form instead
                  </button>
                </div>
              </div>

              <div className="agent-live-panel__right">
                <div className="voice-wave voice-wave--left">
                  <span />
                  <span />
                  <span />
                </div>

                <div className="mic-button mic-button--minimal" aria-hidden="true">
                  <svg
                    viewBox="0 0 24 24"
                    className="mic-svg"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 15a3 3 0 0 0 3-3V7a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" />
                    <path d="M19 11a7 7 0 0 1-14 0" />
                    <path d="M12 18v3" />
                    <path d="M8 21h8" />
                  </svg>
                </div>
              </div>
            </div>
          </section>
        )}

        {viewMode === "form_setup" && (
          <div
            className={`stage-shell ${
              stageAnimateIn ? "is-visible" : "is-exiting"
            }`}
          >
            <section className="form-stage-intro">
              <div className="form-stage-intro__eyebrow">Step 1 of 2</div>
              <h1 className="form-stage-intro__title">
                A few quick details first
              </h1>
              <p className="form-stage-intro__text">
                Takes less than a minute. Your review helps other travelers
                decide.
              </p>
            </section>

            <OverallRating
              label="How was your stay overall?"
              value={answers.q_overall}
              onChange={(value) => handleQuestionChange("q_overall", value)}
              travelType={travelType}
              onTravelTypeChange={setTravelType}
            >
              {session.stayUsageQuestion && (
                <div className="travel-block">
                  <div className="travel-label">
                    {session.stayUsageQuestion.label}
                  </div>

                  <div className="chip-group">
                    {session.stayUsageQuestion.options.map((option) => (
                      <button
                        key={option}
                        type="button"
                        className={`chip-button ${
                          stayUsage.includes(option) ? "is-selected" : ""
                        }`}
                        onClick={() => handleToggleStayUsage(option)}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </OverallRating>

            <div className="setup-actions setup-actions--single">
              <button
                type="button"
                className="submit-review-button submit-review-button--yellow"
                disabled={!setupComplete}
                onClick={() => switchStage("form_questions")}
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {viewMode === "form_questions" && (
          <div
            className={`stage-shell ${
              stageAnimateIn ? "is-visible" : "is-exiting"
            }`}
          >
            <section className="form-stage-intro form-stage-intro--question-stage">
              <div className="form-stage-intro__split">
                <div className="form-stage-intro__content">
                  <div className="form-stage-intro__eyebrow">Step 2 of 2</div>
                  <h1 className="form-stage-intro__title">Just two questions</h1>
                  <p className="form-stage-intro__text">
                    A sentence or two is enough.
                  </p>
                </div>

                <button
                  type="button"
                  className="text-link-button text-link-button--back"
                  onClick={() => switchStage("form_setup")}
                >
                  Back
                </button>
              </div>
            </section>

            {currentQuestion && (
              <QuestionCard
                key={currentQuestion.id}
                question={currentQuestion}
                value={answers[currentQuestion.id]}
                onChange={handleQuestionChange}
                currentIndex={currentQuestionIndex}
                total={textQuestions.length}
                onNext={handleNextQuestion}
                onSkip={handleSkipQuestion}
                animateIn={questionAnimateIn}
              />
            )}

            <section className="review-card">
              <div className="section-kicker">Optional</div>
              <h2 className="section-title section-title--compact">
                Photos (optional)
              </h2>
              <div className="photo-dropzone">
                <div className="photo-dropzone__icon">📷</div>
                <div className="photo-dropzone__text">
                  Add photos if you'd like
                </div>
              </div>
            </section>

            <button
              type="button"
              className="submit-review-button submit-review-button--yellow"
              onClick={handleSubmit}
            >
              Submit review
            </button>
          </div>
        )}
      </main>
    </div>
  );
}