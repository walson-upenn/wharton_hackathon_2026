import { useEffect, useMemo, useRef, useState } from "react";
import { useConversation } from "@elevenlabs/react";
import {
  buildElevenLabsContextUpdate,
  buildElevenLabsFirstMessage,
  buildElevenLabsPrompt,
} from "../data/elevenLabsPrompt";
import { PROPERTY_PHOTOS, FALLBACK_PHOTO, getPropertyPhoto } from "../data/propertyPhotos";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

// Preload all property photos as soon as the module is parsed
[...Object.values(PROPERTY_PHOTOS), FALLBACK_PHOTO].forEach((url) => {
  const img = new Image();
  img.src = url;
});

function stripToneDirections(text) {
  return text.replace(/\[[^\]]*\]/g, "").replace(/\s{2,}/g, " ").trim();
}

function getMessageText(message) {
  if (!message) return "";
  if (typeof message === "string") return stripToneDirections(message);
  return stripToneDirections(
    (
      message.message ||
      message.text ||
      message.transcript ||
      message.content ||
      message.data?.text ||
      message.data?.transcript ||
      ""
    ).trim()
  );
}

function isFinalUserTranscript(message) {
  if (!message || typeof message === "string") return false;
  const type = String(message.type || message.event || "").toLowerCase();
  const source = String(message.source || message.role || message.speaker || "").toLowerCase();
  const text = getMessageText(message);
  const isUser =
    source === "user" ||
    source === "human" ||
    source === "client" ||
    type.includes("user_transcript");
  const isTentative =
    message.is_final === false ||
    message.isFinal === false ||
    message.final === false ||
    message.tentative === true;
  return isUser && !isTentative && text.length > 0;
}

function getMessageSource(message) {
  return String(message?.source || message?.role || message?.type || "unknown").toLowerCase();
}

function isAgentMessage(message) {
  const source = getMessageSource(message);
  return source === "ai" || source === "agent" || source === "assistant";
}

function getDisplaySource(source) {
  const normalized = String(source || "").toLowerCase();
  if (normalized === "ai" || normalized === "agent" || normalized === "assistant") return "AI";
  if (normalized === "user" || normalized === "human" || normalized === "client") return "User";
  if (!normalized) return "Unknown";
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

export default function VoiceReviewPanel({ session, onFallback, onVoiceComplete }) {
  const [voiceError, setVoiceError] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [visibleTranscriptMessages, setVisibleTranscriptMessages] = useState([]);
  const [conversationId, setConversationId] = useState("");

  const startedRef = useRef(false);
  const gotUserTranscriptRef = useRef(false);
  const transcriptRef = useRef([]);
  const pendingAgentMessageRef = useRef(null);
  const sawAgentSpeakingRef = useRef(false);
  const agentDisplayTimerRef = useRef(null);
  const isSpeakingRef = useRef(false);
  const fallbackHandledRef = useRef(false);
  const completionHandledRef = useRef(false);

  const agentContext = useMemo(
    () => session.elevenLabsContext || {},
    [session.elevenLabsContext]
  );
  const agentPrompt = useMemo(
    () => buildElevenLabsPrompt({ agentContext, property: session.property }),
    [agentContext, session.property]
  );
  const agentFirstMessage = useMemo(
    () => buildElevenLabsFirstMessage({ agentContext, property: session.property }),
    [agentContext, session.property]
  );
  const agentContextUpdate = useMemo(
    () => buildElevenLabsContextUpdate({ agentContext, property: session.property }),
    [agentContext, session.property]
  );

  const photoUrl = getPropertyPhoto(session.propertyId);

  const flushPendingAgentMessage = () => {
    if (!pendingAgentMessageRef.current) return;
    if (agentDisplayTimerRef.current) {
      window.clearTimeout(agentDisplayTimerRef.current);
      agentDisplayTimerRef.current = null;
    }

    const nextMessage = pendingAgentMessageRef.current;
    pendingAgentMessageRef.current = null;
    sawAgentSpeakingRef.current = false;
    transcriptRef.current = [...transcriptRef.current, nextMessage];
    setVisibleTranscriptMessages((current) => [...current, nextMessage]);
  };

  const finishWithFallback = async () => {
    if (fallbackHandledRef.current || completionHandledRef.current) return;
    fallbackHandledRef.current = true;
    try {
      if (conversation.status !== "disconnected") await conversation.endSession();
    } catch {}
    onFallback();
  };

  const finishWithVoice = () => {
    if (completionHandledRef.current || fallbackHandledRef.current) return;
    completionHandledRef.current = true;
    onVoiceComplete({
      conversationId: conversationId || conversation.getId?.() || "",
      transcriptMessages: transcriptRef.current,
      completedByVoice: true,
    });
  };

  const conversation = useConversation({
    overrides: {
      agent: {
        prompt: { prompt: agentPrompt },
        firstMessage: agentFirstMessage,
      },
    },
    onConnect: (details = {}) => {
      const nextConversationId =
        typeof details === "string" ? details : details.conversationId;
      startedRef.current = true;
      setIsStarting(false);
      setConversationId(nextConversationId || conversation.getId?.() || "");
      window.setTimeout(() => {
        try {
          conversation.sendContextualUpdate(agentContextUpdate);
        } catch {}
      }, 0);
    },
    onDisconnect: () => {
      if (!startedRef.current) return;
      if (gotUserTranscriptRef.current) {
        finishWithVoice();
        return;
      }
      finishWithFallback();
    },
    onMessage: (message) => {
      const text = getMessageText(message);
      if (!text) return;
      const nextMessage = {
        source: getMessageSource(message),
        text,
      };
      if (isFinalUserTranscript(message)) {
        gotUserTranscriptRef.current = true;
        transcriptRef.current = [...transcriptRef.current, nextMessage];
        setVisibleTranscriptMessages((current) => [...current, nextMessage]);
        return;
      }
      if (isAgentMessage(message)) {
        pendingAgentMessageRef.current = nextMessage;
        sawAgentSpeakingRef.current = isSpeakingRef.current;
        if (agentDisplayTimerRef.current) window.clearTimeout(agentDisplayTimerRef.current);
        agentDisplayTimerRef.current = window.setTimeout(() => {
          if (!isSpeakingRef.current && !sawAgentSpeakingRef.current) flushPendingAgentMessage();
        }, 1800);
      }
    },
    onError: (error) => {
      const message =
        typeof error === "string"
          ? error
          : error?.message || "Voice review could not start.";
      setVoiceError(message);
      setIsStarting(false);
    },
  });

  const requestMicrophone = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
  };

  const getSignedUrl = async () => {
    const response = await fetch(`${API_BASE_URL}/api/elevenlabs/signed-url`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.signedUrl)
      throw new Error(data.error || "Could not start the voice review.");
    return data.signedUrl;
  };

  const handleStart = async () => {
    setVoiceError("");
    setIsStarting(true);
    fallbackHandledRef.current = false;
    completionHandledRef.current = false;
    try {
      await requestMicrophone();
      const signedUrl = await getSignedUrl();
      conversation.startSession({
        signedUrl,
        connectionType: "websocket",
        userId: session.reviewId,
        overrides: {
          agent: {
            prompt: { prompt: agentPrompt },
            firstMessage: agentFirstMessage,
          },
        },
        dynamicVariables: {
          property_name: agentContext.property_name || session.property?.name || "",
          property_location:
            agentContext.property_location || session.property?.location || "",
          target_amenities_json: agentContext.target_amenities_json || "[]",
          question_strategy: agentContext.question_strategy || "",
        },
      });
    } catch (error) {
      setVoiceError(error?.message || "Voice review could not start.");
      setIsStarting(false);
    }
  };

  const handleClose = async () => {
    if (gotUserTranscriptRef.current) {
      try {
        if (conversation.status !== "disconnected") await conversation.endSession();
      } catch {}
      finishWithVoice();
      return;
    }
    await finishWithFallback();
  };

  const statusText = (() => {
    if (isStarting || conversation.status === "connecting") return "Connecting…";
    if (conversation.status === "connected" && conversation.isSpeaking)
      return "Assistant is speaking";
    if (conversation.status === "connected" && conversation.isListening)
      return "Listening";
    if (conversation.status === "connected") return "Voice review is live";
    return "Ready for voice";
  })();

  const hasStarted =
    conversation.status === "connected" || conversation.status === "connecting";

  useEffect(() => {
    isSpeakingRef.current = conversation.isSpeaking;
    if (!pendingAgentMessageRef.current) return;
    if (conversation.isSpeaking) {
      sawAgentSpeakingRef.current = true;
      return;
    }
    if (!sawAgentSpeakingRef.current) return;

    flushPendingAgentMessage();
  }, [conversation.isSpeaking]);

  useEffect(() => {
    return () => {
      if (agentDisplayTimerRef.current) window.clearTimeout(agentDisplayTimerRef.current);
    };
  }, []);

  return (
    <section className="unified-card is-visible">

      {/* Hotel photo header */}
      <div
        className="unified-card__photo"
        style={{ backgroundImage: `url(${photoUrl})` }}
      >
        <div className="unified-card__photo-overlay" />
        <div className="unified-card__photo-content">
          <div className="unified-card__property-name">{session.property?.name}</div>
          <div className="unified-card__property-location">{session.property?.location}</div>
          {session.property?.stayRange && (
            <div className="unified-card__property-pill">{session.property.stayRange}</div>
          )}
        </div>
        <button
          type="button"
          className="unified-card__close"
          onClick={handleClose}
          aria-label="Close voice review"
        >
          ×
        </button>
      </div>

      {/* Voice panel body */}
      <div className="unified-card__body">
        <div className="unified-card__headline">Leave a 30-second voice review</div>
        <div className="unified-card__sub">
          Your voice is not stored — future travelers will only see a written summary.
        </div>

        <div className="agent-live-panel">
          <div className="agent-live-panel__left">
            <div className="agent-live-status">
              <span className={`agent-live-status__dot ${hasStarted ? "is-live" : ""}`} />
              {statusText}
            </div>

            <div className="agent-live-message">
              Your browser will ask for microphone access before the review starts.
            </div>

            {voiceError && <div className="agent-live-error">{voiceError}</div>}

            {visibleTranscriptMessages.length > 0 && (
              <div className="agent-transcript-preview" aria-label="Voice transcript preview">
                {visibleTranscriptMessages.slice(-2).map((message, index) => (
                  <div
                    key={`${message.source}-${index}`}
                    className="agent-transcript-preview__line"
                  >
                    <span>{getDisplaySource(message.source)}:</span> {message.text}
                  </div>
                ))}
              </div>
            )}

            <div className="agent-live-actions">
              {conversation.status === "connected" ? (
                <button
                  type="button"
                  className="neutral-button neutral-button--strong"
                  onClick={handleClose}
                >
                  Finish voice review
                </button>
              ) : (
                <button
                  type="button"
                  className="ai-voice-button"
                  onClick={handleStart}
                  disabled={isStarting || conversation.status === "connecting"}
                >
                  {isStarting || conversation.status === "connecting"
                    ? "Starting..."
                    : "Start voice review"}
                </button>
              )}
              <button type="button" className="form-fallback-button" onClick={finishWithFallback}>
                Use the form instead
              </button>
            </div>
          </div>

          <div className="agent-live-panel__right">
            <div className={`voice-wave voice-wave--left ${hasStarted ? "is-active" : ""}`} aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <button
              type="button"
              className="mic-button mic-button--minimal"
              onClick={conversation.status === "connected" ? handleClose : handleStart}
              disabled={isStarting || conversation.status === "connecting"}
              aria-label={
                conversation.status === "connected" ? "Finish voice review" : "Start voice review"
              }
            >
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
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
