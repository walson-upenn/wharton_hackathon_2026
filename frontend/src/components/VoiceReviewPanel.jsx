import { useMemo, useRef, useState } from "react";
import { useConversation } from "@elevenlabs/react";
import {
  buildElevenLabsContextUpdate,
  buildElevenLabsFirstMessage,
  buildElevenLabsPrompt,
} from "../data/elevenLabsPrompt";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

const PROPERTY_PHOTOS = {
  "9a0043fd": "https://plus.unsplash.com/premium_photo-1715954843149-84d682442e6a?q=80&w=2069&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
  "5f5a0cd8": "https://images.unsplash.com/photo-1467269204594-9661b134dd2b?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8M3x8Z2VybWFueXxlbnwwfHwwfHx8MA%3D%3D",
  "e52d67a7": "https://images.unsplash.com/photo-1639647564912-651e29b8e6ad?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mnx8YmFuZ2tvayUyMGhvdGVsfGVufDB8fDB8fHww",
  "3216b1b7": "https://images.unsplash.com/photo-1759431770496-c0147a6ad769?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8OXx8YmVsbCUyMGdhcmRlbnN8ZW58MHx8MHx8fDA%3D",
  "db38b19b": "https://images.unsplash.com/photo-1634602417388-5dc691fecd4f?q=80&w=2678&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
  "ff26cdda": "https://plus.unsplash.com/premium_photo-1742457752636-f36ed3bb468a?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MTd8fGZyaXNjbyUyMHRleGFzfGVufDB8fDB8fHww",
  "a036cbe1": "https://images.unsplash.com/photo-1630215921793-dfbfd6d8bba7?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NHx8bWJvbWJlbGF8ZW58MHx8MHx8fDA%3D",
  "fa014137": "https://plus.unsplash.com/premium_photo-1675359655209-edb25475ce57?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MXx8bW9udGVyZXl8ZW58MHx8MHx8fDA%3D",
  "f2d8d955": "https://images.unsplash.com/photo-1623008419825-05bcb221e5f4?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8M3x8bmV3JTIwc215cm5hJTIwYmVhY2h8ZW58MHx8MHx8fDA%3D",
  "7d027ef7": "https://plus.unsplash.com/premium_photo-1742457724078-669d91fc6ce3?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MXx8b2NhbGF8ZW58MHx8MHx8fDA%3D",
  "110f01b8": "https://plus.unsplash.com/premium_photo-1661963222829-cf9572881843?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8OXx8cG9tcGVpfGVufDB8fDB8fHwwL",
  "823fb249": "https://plus.unsplash.com/premium_photo-1675975706513-9daba0ec12a8?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MXx8cm9tZXxlbnwwfHwwfHx8MA%3D%3D",
  "3b984f3b": "https://plus.unsplash.com/premium_photo-1697730349278-a77281cd2c0f?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NXx8c2FuJTIwaXNpZHJvfGVufDB8fDB8fHww",
  
};

const FALLBACK_PHOTO = "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=800";

// Preload all property photos as soon as the module is parsed
[...Object.values(PROPERTY_PHOTOS), FALLBACK_PHOTO].forEach((url) => {
  const img = new Image();
  img.src = url;
});

function getMessageText(message) {
  if (!message) return "";
  if (typeof message === "string") return message;
  return (
    message.message ||
    message.text ||
    message.transcript ||
    message.content ||
    message.data?.text ||
    message.data?.transcript ||
    ""
  ).trim();
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

export default function VoiceReviewPanel({ session, onFallback, onVoiceComplete }) {
  const [voiceError, setVoiceError] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [transcriptMessages, setTranscriptMessages] = useState([]);
  const [conversationId, setConversationId] = useState("");

  const startedRef = useRef(false);
  const gotUserTranscriptRef = useRef(false);
  const transcriptRef = useRef([]);
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

  const photoUrl =
    PROPERTY_PHOTOS[session.propertyId?.slice(0, 8)] || FALLBACK_PHOTO;

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
        source: message?.source || message?.role || message?.type || "unknown",
        text,
      };
      transcriptRef.current = [...transcriptRef.current, nextMessage];
      setTranscriptMessages(transcriptRef.current);
      if (isFinalUserTranscript(message)) gotUserTranscriptRef.current = true;
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

            {transcriptMessages.length > 0 && (
              <div className="agent-transcript-preview" aria-label="Voice transcript preview">
                {transcriptMessages.slice(-2).map((message, index) => (
                  <div
                    key={`${message.source}-${index}`}
                    className="agent-transcript-preview__line"
                  >
                    <span>{message.source}:</span> {message.text}
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
            <div className={`voice-wave voice-wave--left ${hasStarted ? "is-active" : ""}`}>
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
      </div>
    </section>
  );
}
