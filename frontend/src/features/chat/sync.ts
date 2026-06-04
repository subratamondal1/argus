"use client";

// Server-side conversation history, for signed-in accounts only. Anonymous users
// keep their history in the browser (Zustand persist), so every function here is a
// no-op without a token. Failures are logged and swallowed — losing a history sync
// must never break the live chat. The store stays the in-memory source of truth;
// this layer mirrors it to (and from) the backend, keyed by the JWT's tenant.

import { API_BASE } from "@/shared/lib/api";
import { logger } from "@/shared/lib/logger";

import { authHeader, useAuthStore } from "../auth/store";
import { type Conversation, type Turn, useChatStore } from "./store";

// Conversation ids whose full turns are already in the store (loaded from the
// server or authored locally this session), so opening them skips a refetch.
const hydrated = new Set<string>();
const saveTimers = new Map<string, ReturnType<typeof setTimeout>>();

interface SummaryDTO {
  id: string;
  title: string;
  updated_at: number;
}

function signedIn(): boolean {
  return useAuthStore.getState().token !== null;
}

// The durable slice of a turn: its question/answer/sources, not the live event
// stream or transient status flags, which are a streaming concern only.
function persistable(turn: Turn): Record<string, unknown> {
  return {
    id: turn.id,
    question: turn.question,
    deep: turn.deep,
    answer: turn.answer,
    sources: turn.sources,
    artifact: turn.artifact,
    related: turn.related,
  };
}

// Rebuild a full Turn from a persisted slice, defaulting the streaming-only fields.
function rehydrateTurn(raw: Record<string, unknown>): Turn {
  return {
    id: String(raw.id ?? crypto.randomUUID()),
    question: String(raw.question ?? ""),
    deep: Boolean(raw.deep),
    events: [],
    answer: String(raw.answer ?? ""),
    sources: Array.isArray(raw.sources) ? (raw.sources as Turn["sources"]) : [],
    artifact: (raw.artifact as Turn["artifact"]) ?? null,
    related: Array.isArray(raw.related) ? (raw.related as string[]) : [],
    status: "done",
    error: null,
  };
}

// Pull the account's history into the store. Replaces whatever was cached locally
// (anonymous chats or a previous account), so a signed-in user only ever sees
// their own conversations.
export async function loadConversations(): Promise<void> {
  if (!signedIn()) return;
  try {
    const response = await fetch(`${API_BASE}/api/conversations`, { headers: { ...authHeader() } });
    if (!response.ok) return;
    const body = (await response.json()) as { conversations: SummaryDTO[] };
    hydrated.clear();
    const conversations: Conversation[] = body.conversations.map((summary) => ({
      id: summary.id,
      title: summary.title,
      createdAt: summary.updated_at,
      turns: [],
    }));
    useChatStore.getState().replaceConversations(conversations, null);
  } catch (caught) {
    logger.error("history load failed", caught);
  }
}

// Open a conversation, fetching its turns on first access (the list endpoint
// returns titles only, so the sidebar stays cheap).
export async function openConversation(id: string): Promise<void> {
  useChatStore.getState().setActive(id);
  if (!signedIn() || hydrated.has(id)) return;
  try {
    const response = await fetch(`${API_BASE}/api/conversations/${id}`, {
      headers: { ...authHeader() },
    });
    if (!response.ok) return;
    const body = (await response.json()) as { turns: Record<string, unknown>[] };
    useChatStore.getState().setTurns(id, body.turns.map(rehydrateTurn));
    hydrated.add(id);
  } catch (caught) {
    logger.error("history open failed", caught);
  }
}

// Mirror a conversation to the server, debounced so the per-token streaming
// patches collapse into one write when the turn settles.
export function saveConversation(id: string): void {
  if (!signedIn()) return;
  hydrated.add(id); // the store now holds this conversation's authoritative turns
  const pending = saveTimers.get(id);
  if (pending !== undefined) clearTimeout(pending);
  saveTimers.set(
    id,
    setTimeout(() => {
      saveTimers.delete(id);
      void flush(id);
    }, 500),
  );
}

async function flush(id: string): Promise<void> {
  const conversation = useChatStore.getState().conversations.find((item) => item.id === id);
  if (conversation === undefined) return;
  const turns = conversation.turns.filter((turn) => turn.status === "done").map(persistable);
  if (turns.length === 0) return; // nothing worth keeping yet (empty/aborted chat)
  try {
    await fetch(`${API_BASE}/api/conversations/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify({ title: conversation.title, turns }),
    });
  } catch (caught) {
    logger.error("history save failed", caught);
  }
}

export async function removeConversation(id: string): Promise<void> {
  useChatStore.getState().deleteConversation(id);
  hydrated.delete(id);
  if (!signedIn()) return;
  try {
    await fetch(`${API_BASE}/api/conversations/${id}`, {
      method: "DELETE",
      headers: { ...authHeader() },
    });
  } catch (caught) {
    logger.error("history delete failed", caught);
  }
}

// Sign out: drop the token, then wipe the local cache so the account's chats don't
// linger in the browser for whoever uses it next.
export function signOut(): void {
  useAuthStore.getState().logout();
  hydrated.clear();
  useChatStore.getState().replaceConversations([], null);
}
