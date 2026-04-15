import { useEffect, useMemo, useState } from "react";
import "./App.css";
import ReviewHeader from "./components/ReviewHeader";
import PropertyCard from "./components/PropertyCard";
import OverallRating from "./components/OverallRating";
import QuestionCard from "./components/QuestionCard";
import VoiceReviewPanel from "./components/VoiceReviewPanel";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:5000";

function buildQuestionsForUsage(session, stayUsage) {
  const selected = session.targetAmenities.filter((target) =>
    stayUsage.includes(target.amenity)
  );

  return selected.slice(0, 2).map((target, index) => ({
    id: `q_${index + 1}`,
    type: "text",
    amenity: target.amenity,
    label: `What should future travelers know about the ${target.amenity}?`,
    placeholder: "Share one or two specific details",
    askReason: target.ask_reason,
    required: false,
  }));
}

export default function App() {
  const [session, setSession] = useState(null);
  const [properties, setProperties] = useState([]);
  const [selectedPropertyId, setSelectedPropertyId] = useState("");
  const [loadError, setLoadError] = useState("");

  const [viewMode, setViewMode] = useState("agent");
  const [stageAnimateIn, setStageAnimateIn] = useState(true);
  const [questionAnimateIn, setQuestionAnimateIn] = useState(true);

  const [travelType, setTravelType] = useState("");
  const [stayUsage, setStayUsage] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [voiceReview, setVoiceReview] = useState(null);
  const [submissionStatus, setSubmissionStatus] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [answers, setAnswers] = useState({
    q_overall: 0,
  });

  useEffect(() => {
    async function loadProperties() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/properties`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not load properties.");
        setProperties(data);
      } catch (error) {
        setLoadError(error.message);
      }
    }

    loadProperties();
  }, []);

  useEffect(() => {
    async function loadSession() {
      setLoadError("");
      const suffix = selectedPropertyId ? `/${selectedPropertyId}` : "";

      try {
        const response = await fetch(`${API_BASE_URL}/api/review-session${suffix}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not load review session.");

        setSession(data);
        setSelectedPropertyId(data.propertyId);
        setViewMode("agent");
        setTravelType("");
        setStayUsage([]);
        setCurrentQuestionIndex(0);
        setVoiceReview(null);
        setSubmissionStatus("");
        setIsSubmitting(false);
        setAnswers({ q_overall: 0 });
      } catch (error) {
        setLoadError(error.message);
      }
    }

    loadSession();
  }, [selectedPropertyId]);

  const textQuestions = useMemo(() => {
    if (!session) return [];
    if (!stayUsage.length) return session.questions;

    const usageQuestions = buildQuestionsForUsage(session, stayUsage);
    return usageQuestions.length ? usageQuestions : session.questions;
  }, [session, stayUsage]);

  useEffect(() => {
    if (currentQuestionIndex >= textQuestions.length) {
      setCurrentQuestionIndex(0);
    }
  }, [currentQuestionIndex, textQuestions.length]);

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

  const handlePreviousQuestion = () => {
    if (currentQuestionIndex > 0) {
      triggerQuestionTransition(currentQuestionIndex - 1);
    }
  };

  const extractVoiceReview = async (review) => {
    const response = await fetch(`${API_BASE_URL}/api/reviews/voice/extract`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        propertyId: session.propertyId,
        conversationId: review.conversationId,
        transcriptMessages: review.transcriptMessages,
        targetAmenities: session.targetAmenities,
      }),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not extract voice review.");
    return data;
  };

  const handleSubmit = async () => {
    if (!answers.q_overall && !voiceReview?.completedByVoice) {
      setSubmissionStatus("Add an overall rating before submitting.");
      return;
    }

    const payload = {
      reviewId: session.reviewId,
      propertyId: session.propertyId,
      travelType,
      stayUsage,
      answers,
      targetAmenities: session.targetAmenities,
      voice: voiceReview,
    };

    try {
      setIsSubmitting(true);
      setSubmissionStatus("Wrapping up your review...");
      let extraction = null;

      if (voiceReview?.completedByVoice) {
        extraction = await extractVoiceReview(voiceReview);
      }

      console.log("submit payload:", { ...payload, extraction });
      setSubmissionStatus("");
      switchStage("submitted");
    } catch {
      console.log("submit payload:", payload);
      setSubmissionStatus("Saved for the demo. Transcript extraction can run when API keys are available.");
      switchStage("submitted");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loadError) {
    return (
      <div className="page-shell">
        <ReviewHeader />
        <main className="page-content">
          <section className="review-card">
            <div className="section-kicker">Setup issue</div>
            <h1 className="section-title">Could not load the dynamic review flow</h1>
            <p className="form-stage-intro__text">{loadError}</p>
          </section>
        </main>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="page-shell">
        <ReviewHeader />
        <main className="page-content">
          <section className="review-card">
            <div className="section-kicker">Loading</div>
            <h1 className="section-title">Preparing your review</h1>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <ReviewHeader />

      <main className="page-content">
        <div className="top-meta-line">
          <span className="top-meta-line__muted">Write a review</span>
        </div>

        {properties.length > 0 && (
          <label className="property-picker">
            <span>Demo property</span>
            <select
              value={selectedPropertyId}
              onChange={(event) => setSelectedPropertyId(event.target.value)}
            >
              {properties.map((property) => (
                <option key={property.property_id} value={property.property_id}>
                  {property.city || "Hotel"} · {property.property_id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
        )}

        <PropertyCard property={session.property} />

        {viewMode === "agent" && (
          <div className={stageAnimateIn ? "is-visible" : "is-exiting"}>
            <VoiceReviewPanel
              key={session.propertyId}
              session={session}
              onFallback={() => switchStage("form_setup")}
              onVoiceComplete={(review) => {
                setVoiceReview(review);
                switchStage("voice_complete");
              }}
            />
          </div>
        )}

        {viewMode === "voice_complete" && (
          <div
            className={`stage-shell ${
              stageAnimateIn ? "is-visible" : "is-exiting"
            }`}
          >
            <section className="review-card voice-complete-card">
              <div className="section-kicker">Voice review saved</div>
              <h1 className="section-title">Your voice review is ready</h1>
              <p className="voice-complete-card__text">
                We captured your response. You can send it now or add a few
                written details first.
              </p>

              {submissionStatus && (
                <div className="voice-complete-card__meta">{submissionStatus}</div>
              )}

              <div className="agent-live-actions">
                <button
                  type="button"
                  className="submit-review-button submit-review-button--yellow"
                  onClick={handleSubmit}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Submitting..." : "Submit review"}
                </button>

                <button
                  type="button"
                  className="neutral-button"
                  onClick={() => switchStage("form_setup")}
                >
                  Add more details
                </button>
              </div>
            </section>
          </div>
        )}

        {viewMode === "submitted" && (
          <div
            className={`stage-shell ${
              stageAnimateIn ? "is-visible" : "is-exiting"
            }`}
          >
            <section className="review-card review-submitted-card">
              <div className="section-kicker">Review submitted</div>
              <h1 className="section-title">Thanks for helping future travelers</h1>
              <p className="voice-complete-card__text">
                Your feedback helps answer the details people look for before they book.
              </p>

              {submissionStatus && (
                <div className="voice-complete-card__meta">{submissionStatus}</div>
              )}
            </section>
          </div>
        )}

        {viewMode === "form_setup" && (
          <div
            className={`stage-shell ${
              stageAnimateIn ? "is-visible" : "is-exiting"
            }`}
          >
            <section className="form-stage-intro stage-header">
              <div className="form-stage-intro__eyebrow">Step 1 of 2</div>
              <h1 className="form-stage-intro__title">
                A few quick details first
              </h1>
              <p className="form-stage-intro__text">
                We will only ask about amenities you actually used.
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
            <section className="form-stage-intro stage-header stage-header--with-action">
              <div className="form-stage-intro__content">
                <div className="form-stage-intro__eyebrow">Step 2 of 2</div>
                <h1 className="form-stage-intro__title">Just two questions</h1>
                <p className="form-stage-intro__text">
                  A sentence or two is enough.
                </p>
              </div>

              <button
                type="button"
                className="stage-back-button"
                onClick={() => switchStage("form_setup")}
              >
                Back
              </button>
            </section>

            {currentQuestion && (
              <QuestionCard
                key={currentQuestion.id}
                question={currentQuestion}
                value={answers[currentQuestion.id] || ""}
                onChange={handleQuestionChange}
                currentIndex={currentQuestionIndex}
                total={textQuestions.length}
                onNext={handleNextQuestion}
                onPreviousQuestion={handlePreviousQuestion}
                animateIn={questionAnimateIn}
              />
            )}

            <section className="review-card">
              <div className="section-kicker">Optional</div>
              <h2 className="section-title section-title--compact">
                Photos (optional)
              </h2>
              <div className="photo-dropzone">
                <div className="photo-dropzone__text">
                  Add photos if you'd like
                </div>
              </div>
            </section>

            {submissionStatus && (
              <div className="voice-complete-card__meta">{submissionStatus}</div>
            )}

            <button
              type="button"
              className="submit-review-button submit-review-button--yellow"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Submitting..." : "Submit review"}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
