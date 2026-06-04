"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { AgentEvent, ChatStatus, Source } from "./types";

export interface Artifact {
  title: string;
  kind: string;
  content: string;
}

export interface Turn {
  id: string;
  question: string;
  deep: boolean;
  events: AgentEvent[];
  answer: string;
  sources: Source[];
  artifact: Artifact | null;
  related: string[];
  status: ChatStatus;
  // True while the agent is verifying/refining a streamed draft (the reflection
  // pass): the displayed answer is the prior draft, held and dimmed until the
  // refined one starts streaming. Optional so older persisted turns default off.
  refining?: boolean;
  error: string | null;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  turns: Turn[];
}

interface ChatState {
  conversations: Conversation[];
  activeId: string | null;
  hydrated: boolean;
  newConversation: () => string;
  setActive: (id: string) => void;
  deleteConversation: (id: string) => void;
  addTurn: (conversationId: string, turn: Turn) => void;
  patchTurn: (conversationId: string, turnId: string, patch: Partial<Turn>) => void;
  // Replace the whole list (server history on login; emptied on logout) and
  // lazily fill a conversation's turns once they're fetched from the server.
  replaceConversations: (conversations: Conversation[], activeId: string | null) => void;
  setTurns: (conversationId: string, turns: Turn[]) => void;
}

function uuid(): string {
  return typeof crypto !== "undefined" ? crypto.randomUUID() : `${Math.random()}`;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeId: null,
      hydrated: false,

      // Reuse an existing empty conversation instead of stacking up duplicate
      // "New chat" entries — clicking New chat with nothing typed just keeps you
      // on the one empty chat. A conversation gets a real title on its first turn.
      newConversation: () => {
        const empty = get().conversations.find((conversation) => conversation.turns.length === 0);
        if (empty !== undefined) {
          set({ activeId: empty.id });
          return empty.id;
        }
        const id = uuid();
        set((state) => ({
          conversations: [
            { id, title: "New chat", createdAt: Date.now(), turns: [] },
            ...state.conversations,
          ],
          activeId: id,
        }));
        return id;
      },

      setActive: (id) => set({ activeId: id }),

      deleteConversation: (id) =>
        set((state) => {
          const conversations = state.conversations.filter((c) => c.id !== id);
          const activeId = state.activeId === id ? (conversations[0]?.id ?? null) : state.activeId;
          return { conversations, activeId };
        }),

      addTurn: (conversationId, turn) =>
        set((state) => ({
          conversations: state.conversations.map((conversation) =>
            conversation.id === conversationId
              ? {
                  ...conversation,
                  title:
                    conversation.turns.length === 0
                      ? turn.question.slice(0, 60)
                      : conversation.title,
                  turns: [...conversation.turns, turn],
                }
              : conversation,
          ),
        })),

      patchTurn: (conversationId, turnId, patch) =>
        set((state) => ({
          conversations: state.conversations.map((conversation) =>
            conversation.id === conversationId
              ? {
                  ...conversation,
                  turns: conversation.turns.map((turn) =>
                    turn.id === turnId ? { ...turn, ...patch } : turn,
                  ),
                }
              : conversation,
          ),
        })),

      replaceConversations: (conversations, activeId) => set({ conversations, activeId }),

      setTurns: (conversationId, turns) =>
        set((state) => ({
          conversations: state.conversations.map((conversation) =>
            conversation.id === conversationId ? { ...conversation, turns } : conversation,
          ),
        })),
    }),
    {
      name: "argus-chat",
      version: 1,
      // Turns saved before the sources field existed rehydrate without it;
      // backfill an empty array so reads never hit undefined.
      migrate: (persisted) => {
        const state = persisted as { conversations?: Conversation[] } | undefined;
        if (state?.conversations) {
          for (const conversation of state.conversations) {
            for (const turn of conversation.turns) {
              if (turn.sources === undefined) turn.sources = [];
            }
          }
        }
        return state as ChatState;
      },
      partialize: (state) => ({
        activeId: state.activeId,
        conversations: state.conversations.map((conversation) => ({
          ...conversation,
          turns: conversation.turns.map((turn) =>
            turn.status === "streaming" ? { ...turn, status: "done" as ChatStatus } : turn,
          ),
        })),
      }),
      onRehydrateStorage: () => (state) => {
        if (state) state.hydrated = true;
      },
    },
  ),
);
