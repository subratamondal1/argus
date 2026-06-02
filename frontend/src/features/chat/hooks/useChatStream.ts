"use client";

import { useCallback, useRef, useState } from "react";

import { API_BASE } from "@/shared/lib/api";
import { logger } from "@/shared/lib/logger";

import type { AgentEvent, ChatStatus } from "../types";

interface ChatStream {
  question: string;
  events: AgentEvent[];
  answer: string;
  status: ChatStatus;
  error: string | null;
  ask: (question: string, deep: boolean) => Promise<void>;
  cancel: () => void;
}

// A fresh token run starts after each of these phase events, so the answer
// buffer is cleared and only the final contiguous stream is shown.
const RESETS_ANSWER = new Set(["plan", "tool", "synthesize"]);

// Streams POST /api/ask as Server-Sent Events. Progress events drive the steps
// view; `token` events stream the answer; the final `answer` event is
// authoritative. The frame parser tolerates both LF and CRLF delimiters.
export function useChatStream(): ChatStream {
  const [question, setQuestion] = useState("");
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const ask = useCallback(async (text: string, deep: boolean) => {
    setQuestion(text);
    setEvents([]);
    setAnswer("");
    setError(null);
    setStatus("streaming");
    logger.breadcrumb(`ask deep=${deep}`);

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const response = await fetch(`${API_BASE}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, deep }),
        signal: controller.signal,
      });
      if (!response.ok || response.body === null) {
        throw new Error(`request failed: HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          for (const line of frame.split(/\r?\n/)) {
            if (!line.startsWith("data:")) continue;
            const payload = line.slice("data:".length).trim();
            if (payload.length > 0) applyEvent(JSON.parse(payload) as AgentEvent);
          }
        }
      }
      setStatus((current) => (current === "error" ? current : "done"));
    } catch (caught) {
      if (caught instanceof Error && caught.name === "AbortError") return;
      const message = caught instanceof Error ? caught.message : "unknown error";
      logger.error("chat stream failed", caught);
      setError(message);
      setStatus("error");
    }

    function applyEvent(event: AgentEvent): void {
      if (event.type === "token") {
        if (typeof event.text === "string") setAnswer((prev) => prev + event.text);
        return;
      }
      if (event.type === "answer") {
        if (typeof event.text === "string") setAnswer(event.text);
        return;
      }
      if (event.type === "error") {
        setError(event.message ?? "agent error");
        setStatus("error");
        return;
      }
      if (event.type === "done") return;
      if (RESETS_ANSWER.has(event.type)) setAnswer("");
      setEvents((prev) => [...prev, event]);
    }
  }, []);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    setStatus((current) => (current === "streaming" ? "done" : current));
  }, []);

  return { question, events, answer, status, error, ask, cancel };
}
