"use client";

import { useCallback, useRef, useState } from "react";

import { API_BASE } from "@/shared/lib/api";
import { logger } from "@/shared/lib/logger";

import type { AgentEvent, ChatStatus } from "../types";

interface ChatStream {
  events: AgentEvent[];
  answer: string;
  status: ChatStatus;
  error: string | null;
  ask: (question: string, deep: boolean) => Promise<void>;
  cancel: () => void;
}

// Streams POST /api/ask as Server-Sent Events: the answer is collected
// separately from the progress events so the UI can render the live agent
// activity and the final answer independently.
export function useChatStream(): ChatStream {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const ask = useCallback(async (question: string, deep: boolean) => {
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
        body: JSON.stringify({ question, deep }),
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
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const dataLine = frame
            .split("\n")
            .find((line) => line.startsWith("data:"));
          if (dataLine === undefined) continue;
          const payload = dataLine.slice("data:".length).trim();
          if (payload.length === 0) continue;
          applyEvent(JSON.parse(payload) as AgentEvent);
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
      if (event.type === "answer" && typeof event.text === "string") {
        setAnswer(event.text);
      } else if (event.type === "error") {
        setError(event.message ?? "agent error");
        setStatus("error");
      } else if (event.type !== "done") {
        setEvents((previous) => [...previous, event]);
      }
    }
  }, []);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    setStatus("idle");
  }, []);

  return { events, answer, status, error, ask, cancel };
}
