import { useEffect, useMemo, useState } from "react";
import "./App.css";
import ReviewHeader from "./components/ReviewHeader";
import PropertyCard from "./components/PropertyCard";
import OverallRating from "./components/OverallRating";
import QuestionCard from "./components/QuestionCard";
import VoiceReviewPanel from "./components/VoiceReviewPanel";
import ProgressBar from "./components/ProgressBar";
import ManagerView from "./components/ManagerView";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

function formatAmenityLabel(amenity) {
  return amenity
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function buildQuestionsForUsage(session, stayUsage) {
  const selected = session.targetAmenities.filter((target) =>
    stayUsage.includes(target.amenity)
  );

  return selected.slice(0, 2).map((target, index) => ({
    id: `q_${target.priority_order || index + 1}`,
    type: "text",
    amenity: target.amenity,
    label:
      target.formQuestion?.primaryQuestion ||
      `What should future travelers know about the ${formatAmenityLabel(target.amenity)}?`,
    placeholder:
      target.formQuestion?.placeholder || "Share one or two specific details",
    askReason: target.formQuestion?.selectionReason || target.ask_reason,
    required: false,
  }));
}

export default function App() {
  const [appMode, setAppMode] = useState("guest");
  const [session, setSession] = useState(null);
  const [properties, setProperties] = useState([]);
  const [sessionsByPropertyId, setSessionsByPropertyId] = useState({});
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

  const [noneOfThese, setNoneOfThese] = useState(false);


  const [answers, setAnswers] = useState({
    q_overall: 0,
  });

  useEffect(() => {
    async function loadReviewData() {
      setLoadError("");

      try {
        const response = await fetch("/data/review-sessions.json");
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || "Could not load precomputed review sessions.");
        }

        const sessions = data.sessions || [];
        const sessionMap = Object.fromEntries(
          sessions.map((item) => [item.propertyId, item])
        );
        const initialSession = sessions[0];

        if (!initialSession) {
          throw new Error("No precomputed review sessions are available.");
        }

        setProperties(data.properties || []);
        setSessionsByPropertyId(sessionMap);
        setSession(initialSession);
        setSelectedPropertyId(initialSession.propertyId);
        setViewMode("agent");
        setTravelType("");
        setStayUsage([]);
        setCurrentQuestionIndex(0);
        setVoiceReview(null);
        setSubmissionStatus("");
        setIsSubmitting(false);
        setAnswers({ q_overall: 0 });
        setNoneOfThese(false);
      } catch (error) {
        setLoadError(error.message);
      }
    }

    loadReviewData();
  }, []);

  useEffect(() => {
    if (!selectedPropertyId) return;
    if (session?.propertyId === selectedPropertyId) return;

    const nextSession = sessionsByPropertyId[selectedPropertyId];
    if (!nextSession) return;

    setSession(nextSession);
    setViewMode("agent");
    setTravelType("");
    setStayUsage([]);
    setCurrentQuestionIndex(0);
    setVoiceReview(null);
    setSubmissionStatus("");
    setIsSubmitting(false);
    setAnswers({ q_overall: 0 });
    setNoneOfThese(false);
  }, [selectedPropertyId, session?.propertyId, sessionsByPropertyId]);

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
  (stayUsage.length > 0 || noneOfThese);

  const currentQuestion = textQuestions[currentQuestionIndex];
  const step1Progress = [
  answers.q_overall > 0,
  travelType.length > 0,
  stayUsage.length > 0 || noneOfThese,
].filter(Boolean).length / 3;

const step2Progress = textQuestions.length > 0
  ? textQuestions.filter(q => (answers[q.id] || "").trim().length > 0).length / textQuestions.length
  : 0;

  const handleQuestionChange = (questionId, value) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  const handleToggleStayUsage = (option) => {
  setNoneOfThese(false);
  setStayUsage((prev) =>
    prev.includes(option)
      ? prev.filter((item) => item !== option)
      : [...prev, option]
  );
};

const handleNoneOfThese = () => {
  setNoneOfThese((prev) => {
    if (!prev) setStayUsage([]);
    return !prev;
  });
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

  if (appMode === "manager") {
    return (
      <div className="page-shell">
        <ReviewHeader />
        <div className="mode-toggle-bar">
          <button
            className="mode-toggle-btn"
            onClick={() => setAppMode("guest")}
          >
            Guest view
          </button>
          <button
            className="mode-toggle-btn mode-toggle-btn--active"
            disabled
          >
            Manager view
          </button>
        </div>
        <ManagerView
          propertyId={selectedPropertyId}
          properties={properties}
          onPropertyChange={setSelectedPropertyId}
        />
      </div>
    );
  }

  return (
    <div className="page-shell">
      <ReviewHeader />

      <div className="mode-toggle-bar">
        <button
          className="mode-toggle-btn mode-toggle-btn--active"
          disabled
        >
          Guest view
        </button>
        <button
          className="mode-toggle-btn"
          onClick={() => setAppMode("manager")}
        >
          Manager view
        </button>
      </div>

      <main className="page-content">

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
            <ProgressBar step={1} stepProgress={step1Progress} />
            <section className="form-stage-intro stage-header">
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
                        {formatAmenityLabel(option)}
                      </button>
                    ))}
                    <button
                    type="button"
                    className={`chip-button chip-button--none ${noneOfThese ? "is-selected" : ""}`}
                    onClick={handleNoneOfThese}
                  >
                    None of these
                  </button>
                  </div>
                </div>
              )}
            </OverallRating>

            <div className="setup-actions--single">
              <button
                type="button"
                className="submit-review-button submit-review-button--yellow"
                disabled={!setupComplete}
                onClick={() => noneOfThese ? handleSubmit() : switchStage("form_questions")}
              >
                {noneOfThese ? "Submit review" : "Continue"}
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
            <ProgressBar step={2} stepProgress={step2Progress} />

            <section className="form-stage-intro stage-header">
              <div className="form-stage-intro__content">
                <h1 className="form-stage-intro__title">Just two questions</h1>
                <p className="form-stage-intro__text">
                  A sentence or two is enough.
                </p>
              </div>
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
                onBack={() => switchStage("form_setup")}
                animateIn={questionAnimateIn}
              />
            )}

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
