"use client";

import { useCallback, useRef } from "react";

import { API_BASE, friendlyError } from "@/shared/lib/api";
import { logger } from "@/shared/lib/logger";

import { useChatStore } from "../store";
import type { AgentEvent } from "../types";

const RESETS_ANSWER = new Set(["plan", "tool"]);

interface Ask {
  ask: (question: string, deep: boolean, ingested?: string[]) => Promise<void>;
  cancel: () => void;
}

// Streams POST /api/ask into a new turn of the active conversation, creating a
// conversation if there isn't one. Progress events drive the steps; token events
// stream the answer. When the agent re-synthesizes after self-verification, the
// prior draft is held on screen (and dimmed via `refining`) and swapped only when
// the new draft's first token lands — so the panel never blanks. SSE frames are
// CRLF-delimited.
export function useAsk(): Ask {
  const controllerRef = useRef<AbortController | null>(null);

  const ask = useCallback(async (question: string, deep: boolean, ingested: string[] = []) => {
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
      sources: [],
      artifact: null,
      related: [],
      status: "streaming",
      error: null,
    });

    let events: AgentEvent[] = [];
    let answer = "";
    // A `synthesize` arms a deferred clear: the previous draft stays on screen
    // (so the panel never blanks during the verify/refine gap) and is replaced
    // only when the first token of the new draft lands.
    let clearOnNextToken = false;

    const apply = (event: AgentEvent): void => {
      if (event.type === "token") {
        if (clearOnNextToken) {
          answer = "";
          clearOnNextToken = false;
        }
        answer += event.text ?? "";
        patch(conversationId, turnId, { answer, refining: false });
        return;
      }
      if (event.type === "synthesize") {
        // Don't wipe the visible draft yet — keep it until the refined draft
        // starts streaming (or the final `answer` arrives).
        clearOnNextToken = true;
        events = [...events, event];
        patch(conversationId, turnId, { events });
        return;
      }
      if (event.type === "review") {
        // Self-verification has begun; hold and dim the current draft.
        events = [...events, event];
        patch(conversationId, turnId, { events, refining: true });
        return;
      }
      if (event.type === "reflect") {
        // Complete -> the streamed draft stands. Incomplete -> a refined draft is
        // coming, so stay in the refining state until its first token.
        events = [...events, event];
        patch(conversationId, turnId, { events, refining: event.complete !== true });
        return;
      }
      if (event.type === "answer") {
        answer = event.text ?? answer;
        clearOnNextToken = false;
        patch(conversationId, turnId, { answer, refining: false });
        return;
      }
      if (event.type === "related") {
        patch(conversationId, turnId, { related: event.questions ?? [] });
        return;
      }
      if (event.type === "sources") {
        patch(conversationId, turnId, { sources: event.items ?? [] });
        return;
      }
      if (event.type === "artifact") {
        patch(conversationId, turnId, {
          artifact: {
            title: event.title ?? "Report",
            kind: event.kind ?? "report",
            content: event.content ?? "",
          },
        });
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
        body: JSON.stringify({ question, deep, ingested }),
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
      patch(conversationId, turnId, { status: "done", refining: false });
    } catch (caught) {
      if (caught instanceof Error && caught.name === "AbortError") {
        patch(conversationId, turnId, { status: "done", refining: false });
        return;
      }
      logger.error("ask failed", caught);
      patch(conversationId, turnId, {
        error: friendlyError(caught),
        status: "error",
        refining: false,
      });
    }
  }, []);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  return { ask, cancel };
}
