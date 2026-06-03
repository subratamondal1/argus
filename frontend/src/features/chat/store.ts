"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { AgentEvent, ChatStatus } from "./types";

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
  artifact: Artifact | null;
  related: string[];
  status: ChatStatus;
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
}

function uuid(): string {
  return typeof crypto !== "undefined" ? crypto.randomUUID() : `${Math.random()}`;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      conversations: [],
      activeId: null,
      hydrated: false,

      newConversation: () => {
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
          const activeId =
            state.activeId === id ? (conversations[0]?.id ?? null) : state.activeId;
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
    }),
    {
      name: "argus-chat",
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
