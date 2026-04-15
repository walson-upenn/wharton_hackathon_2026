import { useMemo, useRef, useState } from "react";
import { useConversation } from "@elevenlabs/react";
import {
  buildElevenLabsContextUpdate,
  buildElevenLabsFirstMessage,
  buildElevenLabsPrompt,
} from "../data/elevenLabsPrompt";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

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

  const finishWithFallback = async () => {
    if (fallbackHandledRef.current || completionHandledRef.current) return;
    fallbackHandledRef.current = true;

    try {
      if (conversation.status !== "disconnected") {
        await conversation.endSession();
      }
    } catch {
      // The SDK may already be disconnected; fallback should still proceed.
    }

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
        prompt: {
          prompt: agentPrompt,
        },
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
        } catch {
          // Context updates are best-effort; the base voice session should continue.
        }
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

      if (isFinalUserTranscript(message)) {
        gotUserTranscriptRef.current = true;
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

    if (!response.ok || !data.signedUrl) {
      throw new Error(data.error || "Could not start the voice review.");
    }

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
            prompt: {
              prompt: agentPrompt,
            },
            firstMessage: agentFirstMessage,
          },
        },
        dynamicVariables: {
          property_name: agentContext.property_name || session.property?.name || "",
          property_location: agentContext.property_location || session.property?.location || "",
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
        if (conversation.status !== "disconnected") {
          await conversation.endSession();
        }
      } catch {
        // Completion can still be recorded with the local transcript.
      }

      finishWithVoice();
      return;
    }

    await finishWithFallback();
  };

  const statusText = (() => {
    if (isStarting || conversation.status === "connecting") return "Connecting voice review";
    if (conversation.status === "connected" && conversation.isSpeaking) return "Assistant is speaking";
    if (conversation.status === "connected" && conversation.isListening) return "Listening";
    if (conversation.status === "connected") return "Voice review is live";
    return "Ready for voice";
  })();

  const hasStarted = conversation.status === "connected" || conversation.status === "connecting";

  return (
    <section className="agent-embed-card is-visible">
      <div className="agent-embed-card__header">
        <div>
          <div className="agent-embed-card__title">Leave a 30-second voice review</div>
          <div className="agent-embed-card__subtitle">
            Talk naturally. We will only ask what helps future travelers.
          </div>
          <div className="agent-embed-card__meta">
            You can switch to the form at any time.
          </div>
        </div>

        <button
          type="button"
          className="agent-close-inline"
          onClick={handleClose}
          aria-label="Close voice review"
          title="Close voice review"
        >
          ×
        </button>
      </div>

      <div className="agent-live-panel">
        <div className="agent-live-panel__left">
          <div className="agent-live-status">
            <span className={`agent-live-status__dot ${hasStarted ? "is-live" : ""}`} />
            {statusText}
          </div>

          <div className="agent-live-message">
            We will ask one or two quick follow-ups by voice. Your browser will ask
            for microphone access before the review starts.
          </div>

          {voiceError && <div className="agent-live-error">{voiceError}</div>}

          {transcriptMessages.length > 0 && (
            <div className="agent-transcript-preview" aria-label="Voice transcript preview">
              {transcriptMessages.slice(-2).map((message, index) => (
                <div key={`${message.source}-${index}`} className="agent-transcript-preview__line">
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
                className="neutral-button neutral-button--strong"
                onClick={handleStart}
                disabled={isStarting || conversation.status === "connecting"}
              >
                {isStarting || conversation.status === "connecting"
                  ? "Starting..."
                  : "Start voice review"}
              </button>
            )}

            <button type="button" className="text-link-button" onClick={finishWithFallback}>
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
    </section>
  );
}
