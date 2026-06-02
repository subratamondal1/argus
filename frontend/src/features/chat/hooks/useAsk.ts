"use client";

import { useCallback, useRef } from "react";

import { API_BASE } from "@/shared/lib/api";
import { logger } from "@/shared/lib/logger";

import { useChatStore } from "../store";
import type { AgentEvent } from "../types";

const RESETS_ANSWER = new Set(["plan", "tool", "synthesize"]);

interface Ask {
  ask: (question: string, deep: boolean) => Promise<void>;
  cancel: () => void;
}

// Streams POST /api/ask into a new turn of the active conversation, creating a
// conversation if there isn't one. Progress events drive the steps; token
// events stream the answer; the answer resets on each phase so only the final
// run shows. SSE frames are CRLF-delimited.
export function useAsk(): Ask {
  const controllerRef = useRef<AbortController | null>(null);

  const ask = useCallback(async (question: string, deep: boolean) => {
    const store = useChatStore.getState();
    const conversationId = store.activeId ?? store.newConversation();
    const turnId = crypto.randomUUID();
    const patch = store.patchTurn;
    store.addTurn(conversationId, {
      id: turnId,
      question,
      deep,
      events: [],
      answer: "",
      related: [],
      status: "streaming",
      error: null,
    });

    let events: AgentEvent[] = [];
    let answer = "";

    const apply = (event: AgentEvent): void => {
      if (event.type === "token") {
        answer += event.text ?? "";
        patch(conversationId, turnId, { answer });
        return;
      }
      if (event.type === "answer") {
        answer = event.text ?? answer;
        patch(conversationId, turnId, { answer });
        return;
      }
      if (event.type === "related") {
        patch(conversationId, turnId, { related: event.questions ?? [] });
        return;
      }
      if (event.type === "error") {
        patch(conversationId, turnId, { error: event.message ?? "agent error", status: "error" });
        return;
      }
      if (event.type === "done") return;
      if (RESETS_ANSWER.has(event.type)) answer = "";
      events = [...events, event];
      patch(conversationId, turnId, { events, answer });
    };

    const controller = new AbortController();
    controllerRef.current = controller;
    logger.breadcrumb(`ask deep=${deep}`);

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
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          for (const line of frame.split(/\r?\n/)) {
            if (!line.startsWith("data:")) continue;
            const payload = line.slice("data:".length).trim();
            if (payload.length > 0) apply(JSON.parse(payload) as AgentEvent);
          }
        }
      }
      patch(conversationId, turnId, { status: "done" });
    } catch (caught) {
      if (caught instanceof Error && caught.name === "AbortError") {
        patch(conversationId, turnId, { status: "done" });
        return;
      }
      logger.error("ask failed", caught);
      patch(conversationId, turnId, {
        error: caught instanceof Error ? caught.message : "unknown error",
        status: "error",
      });
    }
  }, []);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  return { ask, cancel };
}
